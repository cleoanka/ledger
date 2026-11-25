# RESULTS — ölçülen headline sayılar (otoritatif)

> `python scripts/reproduce_results.py` ile üretilir. Elle yazılmaz (Anayasa M6).
> Ayar: seed=7, passes=2, max_train/görev=600, eval_limit=150.
>
> **Navigasyon:** [📄 Proje özeti](ozet.md) · [🗺 Belge haritası](docs/INDEX.md) · [🏛 Mimari](ARCHITECTURE.md) · [🚧 Dürüst sınırlar](docs/LIMITATIONS.md)

## Permuted-digits (alan-artımlı; her görev farklı piksel permütasyonu)

| metrik | **bölgesel (CAS)** | ablasyon (naive-SGD) | EWC (lineer+Fisher) | Replay (lineer+tampon) | LogReg tavanı |
|---|---|---|---|---|---|
| A_N (son ort. doğruluk) | **0.844** | 0.378 | 0.627 | 0.816 | 0.936 |
| BWT (geriye-transfer; 0=unutma yok) | **+0.000** | -0.657 | -0.050 | -0.133 | — |
| bölge sayısı | 3 | 1 | — | — | — |
| bölge-seçiciliği (mean IoU; düşük=ayrık) | 0.167 | — | — | — | — |
| σ̂ sürülen-süreç ardışık-oran (≈kritik; İÇSEL-kritiklik DEĞİL — recurrence yok) | 0.96 | — | — | — | — |
## Split-digits (sınıf-artımlı; 5 görev × 2 sınıf)

| metrik | **bölgesel (CAS)** | ablasyon (naive-SGD) | EWC (lineer+Fisher) | Replay (lineer+tampon) | LogReg tavanı |
|---|---|---|---|---|---|
| A_N (son ort. doğruluk) | **0.444** | 0.270 | 0.196 | 0.701 | 0.970 |
| BWT (geriye-transfer; 0=unutma yok) | **-0.608** | -0.875 | -0.991 | -0.348 | — |
| bölge sayısı | 2 | 1 | — | — | — |
