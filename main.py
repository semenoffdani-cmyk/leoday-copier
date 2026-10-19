name: Copy Financial Posts

on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  copy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install telethon requests

      - name: Run copier
        env:
          API_ID: ${{ secrets.API_ID }}
          API_HASH: ${{ secrets.API_HASH }}
          SESSION: ${{ secrets.SESSION }}
          TARGET_CHANNEL: ${{ secrets.TARGET_CHANNEL }}
          GIGACHAT_CLIENT_ID: ${{ secrets.GIGACHAT_CLIENT_ID }}
          GIGACHAT_CLIENT_SECRET: ${{ secrets.GIGACHAT_CLIENT_SECRET }}
        run: python main.py

      - name: Save history to repository
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          if [ -f history.json ]; then
            git add history.json
            if ! git diff --staged --quiet; then
              git commit -m "Update history [skip ci]"
              git push
            else
              echo "Нет изменений в history.json для сохранения."
            fi
          else
            echo "Файл history.json не найден. Пропускаем сохранение."
          fi
