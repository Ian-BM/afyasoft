from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Medicine, StockMovement, UserProfile

User = get_user_model()


class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = ["name", "price", "quantity", "expiry_date"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "Medicine name", "autocomplete": "off"}
            ),
            "price": forms.NumberInput(
                attrs={"class": "input", "placeholder": "0.00", "step": "0.01", "min": "0"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "input", "placeholder": "0", "min": "0"}
            ),
            "expiry_date": forms.DateInput(attrs={"class": "input", "type": "date"}),
        }


class RestockForm(forms.Form):
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        widget=forms.Select(attrs={"class": "input select"}),
        empty_label="Select medicine…",
    )
    add_quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "Units to add", "min": "1"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medicine"].queryset = Medicine.objects.all().order_by("name")


class AddWorkerForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "Username", "autocomplete": "username"}
        ),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "input", "placeholder": "Email (optional)"}),
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "input", "placeholder": "Password", "autocomplete": "new-password"}
        )
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "input", "placeholder": "Confirm password", "autocomplete": "new-password"}
        )
    )
    role = forms.ChoiceField(
        choices=[
            ("worker", "Worker"),
            ("manager", "Manager / Owner"),
        ],
        initial="worker",
        widget=forms.Select(attrs={"class": "input select"}),
    )
    manager = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "input select"}),
        empty_label="Assign manager (optional)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = User.objects.filter(
            is_active=True,
            pharmacy_profile__role=UserProfile.Role.MANAGER,
        ).order_by("username")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("That username is already in use.")
        return username

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("The two password fields do not match.")
        if data.get("role") != UserProfile.Role.WORKER:
            data["manager"] = None
        return data


class StockAdjustmentForm(forms.Form):
    quantity_change = forms.IntegerField(
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "e.g. -2 or 5", "step": "1"}
        ),
        help_text="Use positive to add stock, negative to reduce stock.",
    )

    def clean_quantity_change(self):
        q = self.cleaned_data["quantity_change"]
        if q == 0:
            raise ValidationError("Quantity change cannot be zero.")
        return q


class ExpiryWriteoffForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "Units expired", "min": "1"}
        ),
    )

    def __init__(self, *args, max_quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_quantity = max_quantity

    def clean_quantity(self):
        q = self.cleaned_data["quantity"]
        if self.max_quantity is not None and q > self.max_quantity:
            raise ValidationError(f"Cannot expire more than {self.max_quantity} units.")
        return q


class StockMovementFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "Search medicine…"}),
    )
    reason = forms.ChoiceField(
        required=False,
        choices=[("", "All reasons")] + list(StockMovement.Reason.choices),
        widget=forms.Select(attrs={"class": "input select"}),
    )


class ReceiptFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Search receipt #, sale #, or staff username…",
            }
        ),
    )
