# Online Fotoğraf Galerisi — Başlangıç

Bu depo, ekip halinde geliştireceğiniz online fotoğraf galerisi projesinin başlangıç iskeletini içerir.

## Hedef (MVP)
- Fotoğraf yükleme ve görüntüleme (albüm ve tek fotoğraf sayfası)
- Küçük ölçek için dosya depolama (ilk aşamada local, sonrasında S3 gibi bir bulut depolama)
- Basit kullanıcı kimlik doğrulama (e-posta ile kayıt/giriş veya OAuth)
- Otomatik küçük resim (thumbnail) üretimi ve önbellekleme

## Hızlı başlangıç (local)

1. Sanal ortam oluşturun ve aktifleştirin:

```bash
python -m venv venv
source venv/bin/activate
```

2. Bağımlılıkları yükleyin:

```bash
pip install -r requirements.txt
```

3. Uygulamayı çalıştırın:

```bash
python app.py
```

Tarayıcıyı açıp http://127.0.0.1:5000 adresini ziyaret edin.

## Katılım ve katkı
- Lütfen `CONTRIBUTING.md` içindeki kuralları okuyun.
- Tüm önemli değişiklikler için bir issue açın ve branch + pull request akışıyla ilerleyin.

## Lisans
MIT — detaylar LICENSE dosyasında.
