# Автообновляемый сравнитель цен (GitHub Pages + Actions)
1) Замените `src/config.json` (base_url и списки feeds на реальные CSV URL).
2) Закоммитьте в ветку main и включите Pages → GitHub Actions.
3) Workflow соберёт `site/` на основе фидов и опубликует каждый час.
Формат CSV смотрите в `data/offers_sample.csv`.
