# BlackSquare

Готовый статический сайт для публикации через GitHub Pages или загрузки на хостинг ZIP-архивом.

## Что внутри

- `index.html` — главная страница сайта.
- `styles.css` — все стили и адаптивная верстка.
- `script.js` — небольшая интерактивность: текущий год, копирование email, плавное появление блоков.
- `assets/logo.svg` — логотип.
- `CNAME` — домен `blacksquare72.ru` для GitHub Pages.
- `.github/workflows/pages.yml` — автоматическая публикация на GitHub Pages.
- `release/blacksquare-site.zip` — ZIP-архив с готовым сайтом для загрузки на хостинг.

## Как открыть локально

Откройте файл `index.html` в браузере.

## Как изменить контакты

В `index.html` замените:

- `hello@example.com`
- `+1 000 000 00 00`
- тексты в блоках сайта

В `script.js` замените значение `email`, чтобы кнопка копирования использовала ваш email.

## Как опубликовать через GitHub Pages

1. Загрузите репозиторий на GitHub.
2. Откройте `Settings` -> `Pages`.
3. В блоке `Build and deployment` выберите `GitHub Actions`.
4. После пуша в ветку `main` workflow `Deploy static site to GitHub Pages` опубликует сайт.

## Как подключить домен blacksquare72.ru через Timeweb

В репозитории уже есть файл `CNAME` со значением:

```text
blacksquare72.ru
```

В Timeweb в DNS-зоне домена добавьте A-записи для основного домена:

```text
@    A    185.199.108.153
@    A    185.199.109.153
@    A    185.199.110.153
@    A    185.199.111.153
```

Для `www.blacksquare72.ru` добавьте CNAME:

```text
www    CNAME    sashatrofimov28-cloud.github.io
```

После этого в GitHub откройте `Settings` -> `Pages`, укажите `blacksquare72.ru` в поле `Custom domain` и включите `Enforce HTTPS`, когда проверка домена пройдет.

## Как пересобрать ZIP-архив

```bash
zip -r release/blacksquare-site.zip \
  index.html styles.css script.js assets robots.txt site.webmanifest .nojekyll CNAME \
  -x "*.DS_Store"
```

Готовый архив можно загрузить на хостинг, который принимает статические сайты.
