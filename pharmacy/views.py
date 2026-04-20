import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .forms import (
    AddWorkerForm,
    ClientRegistrationForm,
    ExpiryWriteoffForm,
    MedicineForm,
    ReceiptFilterForm,
    RestockForm,
    StockAdjustmentForm,
    StockMovementFilterForm,
)
from .models import Medicine, Receipt, Sale, StockMovement, UserProfile
from .permissions import (
    is_pharmacy_admin,
    is_pharmacy_manager,
    pharmacy_admin_required,
    pharmacy_staff_manager_required,
)
from .services import apply_stock_change, complete_sale, parse_offline_uuid

User = get_user_model()


def _tr(request, en, sw):
    return sw if getattr(request, "LANGUAGE_CODE", "en").startswith("sw") else en


def _low_stock_threshold():
    return getattr(settings, "PHARMACY_LOW_STOCK_THRESHOLD", 15)


def _expiry_warning_days():
    return getattr(settings, "PHARMACY_EXPIRY_WARNING_DAYS", 90)


def service_worker(request):
    path = Path(__file__).resolve().parent / "static" / "pharmacy" / "sw.js"
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="application/javascript")


@login_required
def dashboard(request):
    if is_pharmacy_admin(request.user):
        staff_users = User.objects.select_related("pharmacy_profile", "pharmacy_profile__manager").order_by(
            "username"
        )
        return render(
            request,
            "pharmacy/admin_dashboard.html",
            {
                "staff_users": staff_users,
                "total_users": staff_users.count(),
                "active_users": staff_users.filter(is_active=True).count(),
                "manager_count": staff_users.filter(pharmacy_profile__role=UserProfile.Role.MANAGER).count(),
                "worker_count": staff_users.filter(pharmacy_profile__role=UserProfile.Role.WORKER).count(),
            },
        )

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    today = timezone.localdate()
    start = timezone.make_aware(datetime.combine(today, time.min))
    end = start + timedelta(days=1)

    today_sales = (
        Sale.objects.filter(created_at__gte=start, created_at__lt=end).aggregate(
            total=Sum("total"), n=Count("id")
        )
    )
    sales_total = today_sales["total"] or Decimal("0")
    txn_count = today_sales["n"] or 0

    low_qs = Medicine.objects.filter(quantity__lte=_low_stock_threshold()).order_by("quantity")[:8]
    low_stock_count = Medicine.objects.filter(quantity__lte=_low_stock_threshold()).count()

    warn_days = _expiry_warning_days()
    soon = today + timedelta(days=warn_days)
    expiring_soon = Medicine.objects.filter(
        expiry_date__lte=soon, expiry_date__gte=today
    ).count()

    chart_days = []
    chart_vals = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_days.append(d.strftime("%a"))
        day_start = timezone.make_aware(datetime.combine(d, time.min))
        day_end = day_start + timedelta(days=1)
        agg = Sale.objects.filter(created_at__gte=day_start, created_at__lt=day_end).aggregate(
            t=Sum("total")
        )
        chart_vals.append(float(agg["t"] or 0))

    max_val = max(chart_vals) if chart_vals else 0
    max_px = 120
    chart_bars = []
    for i in range(len(chart_days)):
        v = chart_vals[i]
        px = max(4, round(v / max_val * max_px)) if max_val else 4
        chart_bars.append({"label": chart_days[i], "value": v, "px": px})

    recent_sales = Sale.objects.select_related("user").prefetch_related("items")[:5]

    return render(
        request,
        "pharmacy/dashboard.html",
        {
            "sales_total": sales_total,
            "txn_count": txn_count,
            "low_stock_count": low_stock_count,
            "low_stock_items": low_qs,
            "expiring_soon_count": expiring_soon,
            "chart_bars": chart_bars,
            "recent_sales": recent_sales,
            "low_stock_threshold": _low_stock_threshold(),
            "client_name": profile.client_name or request.user.username,
            "pharmacy_name": profile.pharmacy_name or "Afya Soft",
        },
    )


@login_required
def sales_pos(request):
    medicines = Medicine.objects.filter(quantity__gt=0).order_by("name")
    search = (request.GET.get("q") or "").strip()
    if search:
        medicines = medicines.filter(name__icontains=search)

    if request.method == "POST":
        raw = request.POST.get("cart_json", "").strip()
        if not raw:
            messages.error(request, "Cart is empty.")
            return redirect("sales")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid cart data.")

        sale, err, _dup = complete_sale(request.user, payload)
        if err:
            messages.error(request, err)
            return redirect("sales")

        messages.success(
            request,
            _tr(request, "Sale completed successfully.", "Mauzo yamekamilika kwa mafanikio."),
        )
        return redirect("receipt", pk=sale.pk)

    all_stock = list(
        Medicine.objects.filter(quantity__gt=0)
        .order_by("name")
        .values("id", "name", "price", "quantity")
    )
    for m in all_stock:
        m["price"] = str(m["price"])

    return render(
        request,
        "pharmacy/sales.html",
        {
            "medicines": medicines,
            "search": search,
            "medicines_data": all_stock,
        },
    )


@login_required
@require_POST
def sync_sale(request):
    try:
        body = json.loads(request.body.decode())
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    items = body.get("items")
    if not isinstance(items, list) or not items:
        return JsonResponse({"ok": False, "error": "No items in sale."}, status=400)

    offline_uuid = parse_offline_uuid(body.get("offline_uuid"))
    recorded_at = None
    if body.get("recorded_at"):
        recorded_at = parse_datetime(body.get("recorded_at"))
        if recorded_at and timezone.is_naive(recorded_at):
            recorded_at = timezone.make_aware(recorded_at)

    sale, err, duplicate = complete_sale(
        request.user,
        items,
        offline_uuid=offline_uuid,
        client_recorded_at=recorded_at,
    )
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "sale_id": sale.pk,
            "duplicate": duplicate,
        }
    )


@login_required
def receipt(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related("items"), pk=pk)
    receipt_record, _ = Receipt.objects.get_or_create(sale=sale)
    return render(
        request,
        "pharmacy/receipt.html",
        {"sale": sale, "receipt_record": receipt_record},
    )


@login_required
def receipt_by_number(request, receipt_number):
    receipt_record = get_object_or_404(
        Receipt.objects.select_related("sale", "sale__user").prefetch_related("sale__items"),
        receipt_number=receipt_number,
    )
    return render(
        request,
        "pharmacy/receipt.html",
        {"sale": receipt_record.sale, "receipt_record": receipt_record},
    )


@login_required
def receipt_archive(request):
    form = ReceiptFilterForm(request.GET or None)
    qs = (
        Receipt.objects.select_related("sale", "sale__user")
        .prefetch_related("sale__items")
        .order_by("-issued_at", "-id")
    )
    if form.is_valid():
        q = (form.cleaned_data.get("q") or "").strip()
        if q:
            match = Q(receipt_number__icontains=q) | Q(sale__user__username__icontains=q)
            if q.isdigit():
                match = match | Q(sale__id=int(q))
            qs = qs.filter(match)

    return render(
        request,
        "pharmacy/receipt_archive.html",
        {"form": form, "receipts": qs[:300]},
    )


@login_required
def inventory_list(request):
    q = (request.GET.get("q") or "").strip()
    low_only = request.GET.get("low") == "1"

    qs = Medicine.objects.all().order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q))
    if low_only:
        qs = qs.filter(quantity__lte=_low_stock_threshold())

    return render(
        request,
        "pharmacy/inventory_list.html",
        {
            "medicines": qs,
            "search": q,
            "low_only": low_only,
            "low_stock_threshold": _low_stock_threshold(),
        },
    )


@login_required
@pharmacy_admin_required
def stock_adjust(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            change = form.cleaned_data["quantity_change"]
            try:
                with transaction.atomic():
                    locked = Medicine.objects.select_for_update().get(pk=med.pk)
                    apply_stock_change(
                        medicine=locked,
                        quantity_change=change,
                        reason=StockMovement.Reason.ADJUSTMENT,
                        user=request.user,
                    )
            except ValueError as e:
                form.add_error("quantity_change", str(e))
            else:
                messages.success(
                    request,
                    _tr(
                        request,
                        f'Stock adjusted for "{locked.name}" by {change:+d}. New quantity: {locked.quantity}.',
                        f'Stoo ya "{locked.name}" imerekebishwa kwa {change:+d}. Kiasi kipya: {locked.quantity}.',
                    ),
                )
                return redirect("inventory")
    else:
        form = StockAdjustmentForm()
    return render(
        request,
        "pharmacy/stock_adjust.html",
        {"medicine": med, "form": form},
    )


@login_required
@pharmacy_admin_required
def stock_expire(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    if request.method == "POST":
        form = ExpiryWriteoffForm(request.POST, max_quantity=med.quantity)
        if form.is_valid():
            qty = form.cleaned_data["quantity"]
            try:
                with transaction.atomic():
                    locked = Medicine.objects.select_for_update().get(pk=med.pk)
                    apply_stock_change(
                        medicine=locked,
                        quantity_change=-qty,
                        reason=StockMovement.Reason.EXPIRED,
                        user=request.user,
                    )
            except ValueError as e:
                form.add_error("quantity", str(e))
            else:
                messages.success(
                    request,
                    _tr(
                        request,
                        f"Recorded {qty} expired units for {locked.name}. New quantity: {locked.quantity}.",
                        f"Vipande {qty} vilivyoisha muda vya {locked.name} vimehifadhiwa. Kiasi kipya: {locked.quantity}.",
                    ),
                )
                return redirect("inventory")
    else:
        form = ExpiryWriteoffForm(max_quantity=med.quantity)
    return render(
        request,
        "pharmacy/stock_expire.html",
        {"medicine": med, "form": form},
    )


@login_required
@pharmacy_admin_required
def stock_movements(request):
    form = StockMovementFilterForm(request.GET or None)
    qs = StockMovement.objects.select_related("medicine", "user").order_by("-date", "-id")
    if form.is_valid():
        q = (form.cleaned_data.get("q") or "").strip()
        reason = form.cleaned_data.get("reason")
        if q:
            qs = qs.filter(medicine__name__icontains=q)
        if reason:
            qs = qs.filter(reason=reason)
    return render(
        request,
        "pharmacy/stock_movements.html",
        {
            "form": form,
            "movements": qs[:300],
        },
    )


@login_required
def medicine_add(request):
    if request.method == "POST":
        form = MedicineForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                med = form.save()
                if med.quantity > 0:
                    StockMovement.objects.create(
                        medicine=med,
                        quantity_change=med.quantity,
                        reason=StockMovement.Reason.ADJUSTMENT,
                        user=request.user,
                    )
            messages.success(
                request,
                _tr(request, "Medicine added.", "Dawa imeongezwa."),
            )
            return redirect("inventory")
    else:
        form = MedicineForm()
    return render(
        request,
        "pharmacy/medicine_form.html",
        {
            "form": form,
            "title": _tr(request, "Add medicine", "Ongeza dawa"),
            "submit_label": _tr(request, "Save medicine", "Hifadhi dawa"),
        },
    )


@login_required
@pharmacy_admin_required
def medicine_edit(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    if request.method == "POST":
        form = MedicineForm(request.POST, instance=med)
        if form.is_valid():
            with transaction.atomic():
                locked = Medicine.objects.select_for_update().get(pk=med.pk)
                previous_qty = locked.quantity
                updated = form.save()
                diff = updated.quantity - previous_qty
                if diff != 0:
                    StockMovement.objects.create(
                        medicine=updated,
                        quantity_change=diff,
                        reason=StockMovement.Reason.ADJUSTMENT,
                        user=request.user,
                    )
            messages.success(
                request,
                _tr(request, "Medicine updated.", "Dawa imesasishwa."),
            )
            return redirect("inventory")
    else:
        form = MedicineForm(instance=med)
    return render(
        request,
        "pharmacy/medicine_form.html",
        {
            "form": form,
            "medicine": med,
            "title": _tr(request, "Edit medicine", "Hariri dawa"),
            "submit_label": _tr(request, "Save changes", "Hifadhi mabadiliko"),
        },
    )


@login_required
@pharmacy_admin_required
def medicine_delete(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    if request.method == "POST":
        try:
            med.delete()
        except ProtectedError:
            messages.error(
                request,
                _tr(
                    request,
                    "This medicine cannot be removed because it is referenced in past sales.",
                    "Dawa hii haiwezi kufutwa kwa sababu imetumika kwenye mauzo ya awali.",
                ),
            )
            return redirect("inventory")
        messages.success(
            request,
            _tr(request, "Medicine removed.", "Dawa imeondolewa."),
        )
        return redirect("inventory")
    return render(request, "pharmacy/medicine_confirm_delete.html", {"medicine": med})


@login_required
def expiry_list(request):
    today = timezone.localdate()
    warn_days = _expiry_warning_days()
    horizon = today + timedelta(days=warn_days)

    qs = (
        Medicine.objects.filter(expiry_date__lte=horizon)
        .order_by("expiry_date", "name")
    )

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(name__icontains=q)

    items = []
    for m in qs:
        days_left = (m.expiry_date - today).days
        if m.expiry_date < today:
            level = "expired"
        elif days_left <= 30:
            level = "critical"
        elif days_left <= 60:
            level = "warning"
        else:
            level = "notice"
        items.append({"medicine": m, "days_left": days_left, "level": level})

    return render(
        request,
        "pharmacy/expiry.html",
        {"items": items, "search": q, "today": today},
    )


@login_required
@pharmacy_admin_required
def restock(request):
    if request.method == "POST":
        form = RestockForm(request.POST)
        if form.is_valid():
            add = form.cleaned_data["add_quantity"]
            with transaction.atomic():
                med = Medicine.objects.select_for_update().get(pk=form.cleaned_data["medicine"].pk)
                apply_stock_change(
                    medicine=med,
                    quantity_change=add,
                    reason=StockMovement.Reason.RESTOCK,
                    user=request.user,
                )
            messages.success(
                request,
                _tr(
                    request,
                    f'Added {add} units to "{med.name}". New quantity: {med.quantity}.',
                    f'Vipande {add} vimeongezwa kwa "{med.name}". Kiasi kipya: {med.quantity}.',
                ),
            )
            return redirect("restock")
    else:
        form = RestockForm()
    return render(request, "pharmacy/restock.html", {"form": form})


@login_required
def reports(request):
    today = timezone.localdate()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    def total_since(start_date):
        start = timezone.make_aware(datetime.combine(start_date, time.min))
        agg = Sale.objects.filter(created_at__gte=start).aggregate(s=Sum("total"), c=Count("id"))
        return agg["s"] or Decimal("0"), agg["c"] or 0

    week_total, week_count = total_since(week_ago)
    month_total, month_count = total_since(month_ago)

    recent = (
        Sale.objects.annotate(item_count=Count("items"))
        .select_related("user")
        .order_by("-created_at")[:25]
    )

    def sales_total_between(start_date, end_date):
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
        end_dt = timezone.make_aware(datetime.combine(end_date, time.min))
        agg = Sale.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).aggregate(t=Sum("total"))
        return float(agg["t"] or 0)

    daily_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        val = sales_total_between(d, d + timedelta(days=1))
        daily_chart.append({"label": d.strftime("%a"), "value": val})

    week_start = today - timedelta(days=today.weekday())
    weekly_chart = []
    for i in range(7, -1, -1):
        ws = week_start - timedelta(days=i * 7)
        we = ws + timedelta(days=7)
        val = sales_total_between(ws, we)
        weekly_chart.append({"label": ws.strftime("%d %b"), "value": val})

    monthly_chart = []
    for i in range(11, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            y -= 1
            m += 12
        while m > 12:
            y += 1
            m -= 12
        start = datetime(y, m, 1).date()
        if m == 12:
            end = datetime(y + 1, 1, 1).date()
        else:
            end = datetime(y, m + 1, 1).date()
        val = sales_total_between(start, end)
        monthly_chart.append({"label": start.strftime("%b"), "value": val})

    return render(
        request,
        "pharmacy/reports.html",
        {
            "week_total": week_total,
            "week_count": week_count,
            "month_total": month_total,
            "month_count": month_count,
            "recent_sales": recent,
            "report_chart_data": {
                "daily": daily_chart,
                "weekly": weekly_chart,
                "monthly": monthly_chart,
            },
        },
    )


@login_required
@pharmacy_staff_manager_required
def staff_list(request):
    staff_users = User.objects.select_related("pharmacy_profile", "pharmacy_profile__manager")
    if is_pharmacy_manager(request.user):
        staff_users = staff_users.filter(
            Q(pk=request.user.pk) | Q(pharmacy_profile__manager=request.user)
        )
    staff_users = staff_users.order_by("username")
    return render(
        request,
        "pharmacy/staff_list.html",
        {
            "staff_users": staff_users,
        },
    )


@login_required
@pharmacy_staff_manager_required
def staff_add(request):
    if request.method == "POST":
        form = AddWorkerForm(request.POST, current_user=request.user)
        if form.is_valid():
            role = form.cleaned_data["role"]
            if is_pharmacy_manager(request.user):
                role = UserProfile.Role.WORKER
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                email=form.cleaned_data.get("email") or "",
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.manager = form.cleaned_data.get("manager")
            if profile.role != UserProfile.Role.WORKER:
                profile.manager = None
            creator_profile = getattr(request.user, "pharmacy_profile", None)
            if creator_profile and creator_profile.pharmacy_name:
                profile.pharmacy_name = creator_profile.pharmacy_name
            if is_pharmacy_manager(request.user):
                profile.manager = request.user
            profile.client_name = form.cleaned_data["username"]
            profile.save(update_fields=["role", "manager", "pharmacy_name", "client_name"])
            messages.success(
                request,
                _tr(
                    request,
                    f'User “{form.cleaned_data["username"]}” was created successfully.',
                    f'Mtumiaji “{form.cleaned_data["username"]}” ameundwa kwa mafanikio.',
                ),
            )
            return redirect("staff_list")
    else:
        form = AddWorkerForm(current_user=request.user)
    return render(
        request,
        "pharmacy/staff_add.html",
        {"form": form, "title": _tr(request, "Add user", "Ongeza mtumiaji")},
    )


@login_required
@pharmacy_admin_required
@require_POST
def staff_toggle_active(request, user_id):
    target = get_object_or_404(User.objects.select_related("pharmacy_profile"), pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=target)
    action = request.POST.get("action")
    if action not in {"activate", "deactivate"}:
        action = "activate" if not target.is_active else "deactivate"
    if target == request.user and target.is_active and action == "deactivate":
        messages.error(
            request,
            _tr(
                request,
                "You cannot deactivate your own account while logged in.",
                "Huwezi kuzima akaunti yako mwenyewe ukiwa umeingia.",
            ),
        )
        return redirect("staff_list")

    if action == "activate":
        if profile.role == UserProfile.Role.WORKER and profile.manager and not profile.manager.is_active:
            messages.error(
                request,
                _tr(
                    request,
                    "Cannot activate this worker because their manager is inactive.",
                    "Huwezi kuwasha mfanyakazi huyu kwa sababu meneja wake hajawashwa.",
                ),
            )
            return redirect("staff_list")
        target.is_active = True
        target.save(update_fields=["is_active"])
        messages.success(
            request,
            _tr(
                request,
                f'User "{target.username}" is now active.',
                f'Mtumiaji "{target.username}" sasa amewashwa.',
            ),
        )
        return redirect("staff_list")

    target.is_active = False
    target.save(update_fields=["is_active"])
    cascaded = 0
    if profile.role == UserProfile.Role.MANAGER:
        cascaded = User.objects.filter(
            is_active=True,
            pharmacy_profile__role=UserProfile.Role.WORKER,
            pharmacy_profile__manager=target,
        ).update(is_active=False)

    if cascaded:
        messages.success(
            request,
            _tr(
                request,
                f'User "{target.username}" was deactivated. {cascaded} linked worker account(s) were also deactivated.',
                f'Mtumiaji "{target.username}" amezimwa. Akaunti {cascaded} za wafanyakazi waliohusishwa pia zimezimwa.',
            ),
        )
    else:
        messages.success(
            request,
            _tr(
                request,
                f'User "{target.username}" is now inactive.',
                f'Mtumiaji "{target.username}" sasa amezimwa.',
            ),
        )
    return redirect("staff_list")


def register_client(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                email=form.cleaned_data.get("email") or "",
                first_name=form.cleaned_data["client_name"],
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.Role.MANAGER
            profile.client_name = form.cleaned_data["client_name"].strip()
            profile.pharmacy_name = form.cleaned_data["pharmacy_name"].strip()
            profile.subscription_started_on = timezone.localdate()
            profile.subscription_duration_days = 30
            profile.manager = None
            profile.save(
                update_fields=[
                    "role",
                    "client_name",
                    "pharmacy_name",
                    "subscription_started_on",
                    "subscription_duration_days",
                    "manager",
                ]
            )
            auth_login(request, user)
            messages.success(
                request,
                _tr(
                    request,
                    f"Welcome {profile.client_name}. Your pharmacy {profile.pharmacy_name} is ready.",
                    f"Karibu {profile.client_name}. Duka lako la dawa {profile.pharmacy_name} lipo tayari.",
                ),
            )
            return redirect("dashboard")
    else:
        form = ClientRegistrationForm()
    return render(request, "registration/register.html", {"form": form})
