"""Okul çekirdeği URL'leri.

`setup/status/` hem arayüzdeki kurulum kapısının (KurulumKapisi) hem masaüstü
başlatıcısının sağlık denetiminin (`desktop/server.py::HEALTH_PATH`) tek
kaynağıdır — yolu değiştirirken üçü birlikte güncellenir.
"""

from __future__ import annotations

from django.urls import path

from apps.okul import views

urlpatterns = [
    path("setup/status/", views.SetupStatusView.as_view(), name="setup-status"),
]
