# BlackSquare

Готовый статический сайт для публикации через GitHub Pages или загрузки на хостинг ZIP-архивом.

## Что внутри

- `index.html` — главная страница сайта.
- `styles.css` — все стили и адаптивная верстка.
- `script.js` — небольшая интерактивность: текущий год, копирование email, плавное появление блоков.
- `assets/logo.svg` — логотип.
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

## Как подключить свой домен

1. В GitHub откройте `Settings` -> `Pages`.
2. В поле `Custom domain` укажите ваш домен.
3. У регистратора домена настройте DNS-записи по инструкции GitHub Pages.
4. Если хотите хранить домен в репозитории, создайте файл `CNAME` в корне проекта и впишите туда только домен, например:

   ```text
   example.com
   ```

## Как пересобрать ZIP-архив

```bash
zip -r release/blacksquare-site.zip \
  index.html styles.css script.js assets robots.txt site.webmanifest .nojekyll \
  -x "*.DS_Store"
```

Готовый архив можно загрузить на хостинг, который принимает статические сайты.
