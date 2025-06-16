from django import forms
from .models import User

class ProfileForm(forms.ModelForm):
    
    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'avatar']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'block w-full p-2 rounded border border-gray-300',
                'readonly': 'readonly',
            }),
            'username': forms.TextInput(attrs={
                'class': 'block w-full p-2 rounded border border-gray-300',
                'readonly': 'readonly',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'block w-full p-2 rounded border border-gray-300'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'block w-full p-2 rounded border border-gray-300'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'sr-only',
                'id': 'avatar-upload',
                'onchange': 'previewFileName()',
            }),

        }
        labels = {
            'email': 'Email',
            'username': 'Username',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'avatar': 'Avatar',
        }
