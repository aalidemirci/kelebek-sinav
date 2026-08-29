"""Okul çekirdeği view'ları (F0 iskeleti).

F0'da veritabanı modeli yok; kurulum durumu sabittir ve `setup_completed=False`
döner — arayüz her rotayı kurulum sihirbazına yönlendirir (sihirbaz F1'de
gelir). F1'de bu view `SchoolConfig(pk=1)` + sayımlardan beslenen gerçek
`selectors.setup_status()` çağrısına dönüşür (DD kalıbı).
"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class SetupStatusView(APIView):
    """Kurulum durumu — masaüstü sağlık denetimi + arayüz kurulum kapısı."""

    def get(self, request: Request) -> Response:
        return Response(
            {
                "setup_completed": False,
                "school_name": "",
                "has_active_school_year": False,
                "student_count": 0,
                "personnel_count": 0,
            }
        )
