"""
Performance Tests — AI Interview Simulator
Tests response times and system behavior under load.
"""

import pytest
import sys
import os
import uuid
import time
import threading
import psutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_PASSWORD = "TestPass123!"

# Token modül yüklenirken (testler başlamadan önce) bir kez alınır.
# Bu sayede PT-01'in login rate limit'i tükenmeden token hazır olur.
def _init_shared_token():
    email = f"perf_shared_{uuid.uuid4().hex[:8]}@testmail.com"
    client.post("/create-user", json={"email": email, "password": TEST_PASSWORD})
    res = client.post("/login", json={"email": email, "password": TEST_PASSWORD})
    if res.status_code == 200:
        return res.json()["access_token"]
    return None

_SHARED_TOKEN = _init_shared_token()

def get_shared_token():
    """Modül genelinde paylaşılan token — modül yüklenirken bir kez oluşturulur."""
    return _SHARED_TOKEN


# ─────────────────────────────────────────────
# PT-01 — Login Ardışık Yük
# ─────────────────────────────────────────────

class TestLoginPerformance:

    def test_login_10_sequential_requests(self):
        """
        PT-01: 10 ardışık login isteği toplam 10 saniyeden az sürmeli.
        Her istek başarılı (200) veya geçerli hata (401) dönmeli.
        """
        email = f"perf_{uuid.uuid4().hex[:8]}@testmail.com"
        client.post("/create-user", json={"email": email, "password": TEST_PASSWORD})

        start = time.time()
        for _ in range(10):
            res = client.post("/login", json={"email": email, "password": TEST_PASSWORD})
            assert res.status_code in [200, 401, 403, 429]  # 429/403 = rate limit (kabul edilir)
        elapsed = time.time() - start

        print(f"\n  PT-01: 10 login isteği → {elapsed:.2f}sn")
        assert elapsed < 10.0, f"10 login isteği çok yavaş: {elapsed:.2f}sn"

    def test_single_login_response_time(self):
        """
        PT-01b: Tek bir login isteği 2 saniyeden az sürmeli.
        """
        email = f"perf_{uuid.uuid4().hex[:8]}@testmail.com"
        client.post("/create-user", json={"email": email, "password": TEST_PASSWORD})

        start = time.time()
        res = client.post("/login", json={"email": email, "password": TEST_PASSWORD})
        elapsed = time.time() - start

        print(f"\n  PT-01b: Tek login isteği → {elapsed:.3f}sn, status: {res.status_code}")
        assert elapsed < 2.0, f"Login çok yavaş: {elapsed:.3f}sn"
        # 429 = rate limiter devrede (önceki PT-01 testinden kalan limit) — bu da geçerli
        assert res.status_code in [200, 401, 429]


# ─────────────────────────────────────────────
# PT-02 — Profile Paralel Yük
# ─────────────────────────────────────────────

class TestProfilePerformance:

    def test_profile_20_parallel_requests(self):
        """
        PT-02: 20 paralel /profile isteği — hepsi başarılı olmalı,
        toplam süre 10 saniyeden az olmalı.
        """
        token = get_shared_token()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")

        results = []

        def make_request():
            res = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
            results.append(res.status_code)

        start = time.time()
        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        print(f"\n  PT-02: 20 paralel /profile isteği → {elapsed:.2f}sn")
        print(f"  Sonuçlar: {set(results)}")

        assert elapsed < 10.0, f"20 paralel istek çok yavaş: {elapsed:.2f}sn"
        assert all(s == 200 for s in results), f"Bazı istekler başarısız: {results}"

    def test_profile_single_response_time(self):
        """
        PT-02b: Tek bir /profile isteği 1 saniyeden az sürmeli.
        """
        token = get_shared_token()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")

        start = time.time()
        res = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
        elapsed = time.time() - start

        print(f"\n  PT-02b: Tek /profile isteği → {elapsed:.3f}sn")
        assert elapsed < 1.0, f"/profile çok yavaş: {elapsed:.3f}sn"
        assert res.status_code == 200


# ─────────────────────────────────────────────
# PT-03 — Interview Listesi Yük
# ─────────────────────────────────────────────

class TestInterviewListPerformance:

    def test_list_interviews_10_sequential(self):
        """
        PT-03: 10 ardışık GET /interviews isteği toplam 5 saniyeden az sürmeli.
        """
        token = get_shared_token()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")

        start = time.time()
        for _ in range(10):
            res = client.get("/interviews", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 200
        elapsed = time.time() - start

        print(f"\n  PT-03: 10 ardışık /interviews isteği → {elapsed:.2f}sn")
        assert elapsed < 5.0, f"10 liste isteği çok yavaş: {elapsed:.2f}sn"


# ─────────────────────────────────────────────
# PT-04 — Büyük Input
# ─────────────────────────────────────────────

class TestLargeInputPerformance:

    def test_large_input_response_time(self):
        """
        PT-04: 10KB'lık input gönderildiğinde sistem 3 saniyeden az sürede
        yanıt vermeli ve crash olmamalı.
        """
        large_string = "A" * 10000  # ~10KB

        start = time.time()
        res = client.post("/login", json={
            "email": f"{large_string}@test.com",
            "password": large_string,
        })
        elapsed = time.time() - start

        print(f"\n  PT-04: 10KB input → {elapsed:.3f}sn, status: {res.status_code}")
        assert elapsed < 3.0, f"Büyük input işleme çok yavaş: {elapsed:.3f}sn"
        assert res.status_code != 500


# ─────────────────────────────────────────────
# PT-05 — Eş Zamanlı Kayıt
# ─────────────────────────────────────────────

class TestConcurrentRegistration:

    def test_10_concurrent_registrations(self):
        """
        PT-05: 10 kullanıcı aynı anda kayıt olmaya çalışır.
        Hepsi başarılı (200) veya düzgün hata (400/422) dönmeli, crash olmamalı.
        """
        results = []

        def register():
            email = f"perf_{uuid.uuid4().hex[:8]}@testmail.com"
            res = client.post("/create-user", json={
                "email": email,
                "password": TEST_PASSWORD,
            })
            results.append(res.status_code)

        start = time.time()
        threads = [threading.Thread(target=register) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        print(f"\n  PT-05: 10 paralel kayıt → {elapsed:.2f}sn")
        print(f"  Sonuçlar: {results}")

        assert elapsed < 15.0, f"10 paralel kayıt çok yavaş: {elapsed:.2f}sn"
        assert all(s in [200, 400, 422, 429] for s in results), f"Beklenmeyen hata kodu: {results}"
        assert 500 not in results, "Sunucu hatası oluştu!"
        # 429 beklenen davranış: rate-limit koruması aktif
        assert any(s == 429 for s in results), "Rate-limit tetiklenmedi — bekleniyordu"


# ─────────────────────────────────────────────
# PT-06 — CPU / RAM Kullanımı
# ─────────────────────────────────────────────

class TestResourceUsage:

    def test_cpu_ram_under_load(self):
        """
        PT-06: 20 paralel istek sırasında CPU ve RAM kullanımı ölçülür.
        Not: psutil tüm sistemin kaynak kullanımını ölçer.
        Test koşulu: diğer uygulamalar kapalıyken çalıştırılmalıdır.
        CPU < %90, RAM artışı < 500MB olmalı.
        """
        token = get_shared_token()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")

        # Başlangıç değerleri
        cpu_before = psutil.cpu_percent(interval=1)
        ram_before = psutil.virtual_memory().used / (1024 * 1024)  # MB

        # Yük oluştur — 20 paralel /profile isteği
        results = []
        peak_cpu = []

        def make_request():
            res = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
            results.append(res.status_code)
            peak_cpu.append(psutil.cpu_percent())

        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Bitiş değerleri
        cpu_after = psutil.cpu_percent(interval=1)
        ram_after = psutil.virtual_memory().used / (1024 * 1024)  # MB
        ram_delta = ram_after - ram_before
        max_cpu = max(peak_cpu) if peak_cpu else cpu_after

        print(f"\n  PT-06: CPU başlangıç: {cpu_before:.1f}%")
        print(f"  PT-06: CPU peak: {max_cpu:.1f}%")
        print(f"  PT-06: CPU bitiş: {cpu_after:.1f}%")
        print(f"  PT-06: RAM başlangıç: {ram_before:.1f}MB")
        print(f"  PT-06: RAM bitiş: {ram_after:.1f}MB")
        print(f"  PT-06: RAM artışı: {ram_delta:.1f}MB")

        assert max_cpu < 90.0, f"CPU kullanımı çok yüksek: {max_cpu:.1f}%"
        assert ram_delta < 500, f"RAM artışı çok fazla: {ram_delta:.1f}MB"
        assert all(s == 200 for s in results), "Bazı istekler başarısız"
