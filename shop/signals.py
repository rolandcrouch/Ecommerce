
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        # user just created -> make a profile
        Profile.objects.create(user=instance)
    else:
        # user saved again -> make sure a profile exists
        Profile.objects.get_or_create(user=instance)