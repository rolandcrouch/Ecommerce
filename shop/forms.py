from django import forms
from .models import Product, Review, Vendor, Store
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class ProductForm(forms.ModelForm):
    """
    Form used by vendors to create or update products.
    """
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'image']


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ["name", "bio"]


class CustomerRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email","password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "customer"
        if commit:
            user.save()
        return user


class VendorRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    vendor_name = forms.CharField(required=True, max_length=255, label="Vendor Name")
    bio = forms.CharField(required=False, widget=forms.Textarea, label="Vendor Bio")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user



class ReviewForm(forms.ModelForm):
    """
    Form for submitting a product review. Includes rating 
    (1–5) and optional comment.
    """
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 
                                             'form-control', 
                                             'rows': 4}),
        }
        labels = {
            'rating': 'Your Rating',
            'comment': 'Your Review (optional)',
        }


class ForgotUsernameForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            "class": "form-control",      
            "placeholder": "Enter your email"
        })
    )


class PasswordResetRequestForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        email = cleaned.get("email")
        if not username or not email:
            return cleaned

        user = User.objects.filter(
            username__iexact=username, email__iexact=email
        ).first()
        if not user:

            raise forms.ValidationError(
                "No account was found with that username and email."
            )
        self.user = user
        return cleaned
