#!/usr/bin/env python3
"""Generate high-fidelity static design previews using real app CSS."""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "mockups" / "previews"
OUT.mkdir(parents=True, exist_ok=True)

SHELL_HEAD = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{title} — BlackSquare макет</title>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#050505">
  <link rel="stylesheet" href="/static/style.css?v=22">
  <link rel="stylesheet" href="/static/mockups/preview-shell.css">
</head>
<body class="theme-dark preview-mode">
<div class="preview-ribbon"><a href="/design">← Все макеты</a><span>{ribbon}</span></div>
<div class="app-shell">
  <aside class="sidebar" id="sidebar" aria-label="Меню">
    <div class="brand">
      <div class="wordmark">BlackSquare</div>
      <span>директор</span>
    </div>
    <nav>
      <a href="/design/preview/dashboard" class="{nav_dashboard}">Главная</a>
      <a href="/design/preview/calendar" class="{nav_calendar}">Календарь</a>
      <a href="/design/preview/crm" class="{nav_crm}">CRM</a>
      <a href="/design/preview/stock" class="{nav_stock}">Склад</a>
      <a href="/design/preview/analytics" class="{nav_analytics}">Статистика</a>
      <a href="/design/preview/employees" class="{nav_employees}">Сотрудники</a>
      <a href="/design/preview/close" class="{nav_close}">Закрытие</a>
      <a href="/settings">Настройки</a>
    </nav>
    <div class="profile">Вошли как: <b>Директор</b></div>
  </aside>
  <div class="main-wrap">
    <header class="mobile-top">
      <button type="button" class="menu-btn" id="menuBtn" aria-label="Меню">☰</button>
      <div class="wordmark">BlackSquare</div>
    </header>
    <main class="main scrollable has-bottom-nav">
"""

SHELL_FOOT = """
    </main>
    <nav class="bottom-nav" aria-label="Навигация">
      <a href="/design/preview/dashboard" class="bottom-nav-item{bn_dashboard}"><span class="bottom-nav-icon">🏠</span><span>Главная</span></a>
      <a href="/design/preview/calendar" class="bottom-nav-item{bn_calendar}"><span class="bottom-nav-icon">📅</span><span>Записи</span></a>
      <a href="/design/preview/crm" class="bottom-nav-item{bn_crm}"><span class="bottom-nav-icon">👥</span><span>Клиенты</span></a>
      <a href="/design/preview/analytics" class="bottom-nav-item{bn_analytics}"><span class="bottom-nav-icon">📊</span><span>Отчёты</span></a>
      <button type="button" class="bottom-nav-item bottom-nav-more" id="menuBtnBottom" aria-label="Меню"><span class="bottom-nav-icon">☰</span><span>Ещё</span></button>
    </nav>
  </div>
  <div class="sidebar-backdrop" id="sidebarBackdrop" aria-hidden="true"></div>
</div>
<script src="/static/app.js?v=22"></script>
</body>
</html>
"""

PAGES = {
    "dashboard": {
        "title": "Главная",
        "ribbon": "Главная · как в продакшене + блок «Закрыто сегодня»",
        "body": """
<div class="dash-page">
  <header class="dash-header">
    <div>
      <h1>Главная</h1>
      <p class="dash-date">19 июня 2026, четверг</p>
    </div>
    <a href="#" class="dash-bell" aria-label="Профиль">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/></svg>
    </a>
  </header>
  <div class="m-strip">
    <div class="m-card tone-green">
      <div class="m-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg></div>
      <div class="m-text"><span class="m-label">Касса</span><strong class="m-value">48 200 ₽</strong></div>
    </div>
    <div class="m-card tone-blue">
      <div class="m-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 17l6-6 4 4 8-10"/></svg></div>
      <div class="m-text"><span class="m-label">Прибыль</span><strong class="m-value">31 400 ₽</strong></div>
    </div>
    <div class="m-card tone-orange">
      <div class="m-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-6 8-6s8 2 8 6"/></svg></div>
      <div class="m-text"><span class="m-label">ЗП</span><strong class="m-value">12 800 ₽</strong></div>
    </div>
    <div class="m-card tone-purple">
      <div class="m-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/></svg></div>
      <div class="m-text"><span class="m-label">м²</span><strong class="m-value">14,2</strong></div>
    </div>
  </div>
  <nav class="dash-periods scrollable-x">
    <a href="#" class="dash-period active">Сегодня</a>
    <a href="#" class="dash-period">Вчера</a>
    <a href="#" class="dash-period">Неделя</a>
    <a href="#" class="dash-period">Месяц</a>
    <a href="#" class="dash-period">Год</a>
  </nav>
  <section class="dash-section">
    <div class="dash-section-head">
      <h2>Ближайшие записи</h2>
      <a href="/design/preview/calendar" class="dash-link">Смотреть все ›</a>
    </div>
    <div class="dash-appt-list">
      <a class="dash-appt bar-orange" href="/design/preview/close">
        <div class="dash-appt-time"><strong>14:00</strong><span>через 2 ч</span></div>
        <div class="dash-appt-body"><b>Алексей К.</b><span>Тонировка задней части</span><span>Стас</span></div>
        <div class="dash-appt-side"><span class="status-pill pill-orange">Ожидает</span><strong>5 500 ₽</strong></div>
      </a>
      <a class="dash-appt bar-blue" href="#">
        <div class="dash-appt-time"><strong>16:30</strong><span>через 4 ч</span></div>
        <div class="dash-appt-body"><b>Мария Сидорова</b><span>Атермальная плёнка</span><span>Катя</span></div>
        <div class="dash-appt-side"><span class="status-pill pill-blue">Подтверждена</span><strong>6 000 ₽</strong></div>
      </a>
    </div>
  </section>
  <section class="dash-section">
    <div class="dash-section-head">
      <h2>Закрыто сегодня</h2>
      <a href="/design/preview/calendar" class="dash-link">Календарь ›</a>
    </div>
    <div class="dash-appt-list">
      <a class="dash-appt bar-green" href="#">
        <div class="dash-appt-time"><strong>10:00</strong><span>закрыто в 12:40</span></div>
        <div class="dash-appt-body"><b>Иван Петров</b><span>Передние боковые</span><span>Катя</span></div>
        <div class="dash-appt-side"><span class="status-pill pill-green">Закрыт</span><strong>2 500 ₽</strong></div>
      </a>
      <a class="dash-appt bar-green" href="#">
        <div class="dash-appt-time"><strong>11:30</strong><span>закрыто в 13:05</span></div>
        <div class="dash-appt-body"><b>Дмитрий В.</b><span>Тонировка задней части</span><span>Стас</span></div>
        <div class="dash-appt-side"><span class="status-pill pill-green">Закрыт</span><strong>5 500 ₽</strong></div>
      </a>
    </div>
  </section>
</div>
""",
    },
    "calendar": {
        "title": "Календарь",
        "ribbon": "Календарь · таймлайн дня, слоты 10:00–21:00",
        "body": """
<div class="cal-page">
  <header class="cal-header">
    <h1>Календарь</h1>
    <nav class="cal-views"><a href="#" class="cal-view active">День</a><a href="#" class="cal-view">Неделя</a><a href="#" class="cal-view">Месяц</a></nav>
    <label class="cal-pick"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><input type="date" class="cal-pick-input" value="2026-06-19"></label>
  </header>
  <div class="cal-date-nav">
    <a class="cal-nav-btn" href="#">‹</a>
    <div class="cal-date-title"><strong>19 июня 2026, четверг</strong><span>4 записи · 720 мин</span></div>
    <a class="cal-nav-btn" href="#">›</a>
  </div>
  <form class="cal-search"><input name="q" placeholder="Телефон / госномер / имя"></form>
  <div class="cal-timeline-wrap">
    <div class="cal-timeline" style="--cal-height: 792px; --cal-hour: 72px">
      <div class="cal-hours">
        <div class="cal-hour" style="height:var(--cal-hour)">10:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">11:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">12:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">13:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">14:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">15:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">16:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">17:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">18:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">19:00</div>
        <div class="cal-hour" style="height:var(--cal-hour)">20:00</div>
      </div>
      <div class="cal-grid">
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <div class="cal-grid-line" style="height:var(--cal-hour)"></div>
        <a class="cal-event tone-green" style="top:0;height:144px;left:calc(0*(100%/2));width:calc(100%/2 - 4px)" href="/design/preview/close">
          <span class="cal-event-time">10:00 – 12:00</span><b class="cal-event-name">Иван Петров</b>
          <span class="cal-event-service">Передние боковые</span><span class="cal-event-master">Катя</span>
        </a>
        <a class="cal-event tone-green" style="top:108px;height:144px;left:calc(1*(100%/2));width:calc(100%/2 - 4px)" href="#">
          <span class="cal-event-time">11:30 – 13:30</span><b class="cal-event-name">Дмитрий В.</b>
          <span class="cal-event-service">Тонировка задней части</span><span class="cal-event-master">Стас</span>
        </a>
        <a class="cal-event tone-orange" style="top:288px;height:216px;left:calc(0*(100%/2));width:calc(100%/2 - 4px)" href="/design/preview/close">
          <span class="cal-event-time">14:00 – 17:00</span><b class="cal-event-name">Алексей К.</b>
          <span class="cal-event-service">Тонировка задней части</span><span class="cal-event-master">Стас</span>
        </a>
        <a class="cal-event tone-blue" style="top:396px;height:180px;left:calc(1*(100%/2));width:calc(100%/2 - 4px)" href="#">
          <span class="cal-event-time">16:30 – 19:00</span><b class="cal-event-name">Мария Сидорова</b>
          <span class="cal-event-service">Атермальная плёнка</span><span class="cal-event-master">Катя</span>
        </a>
      </div>
    </div>
  </div>
</div>
""",
    },
    "crm": {
        "title": "CRM",
        "ribbon": "CRM · карточки клиентов, фильтры, статусы",
        "body": """
<div class="crm-page">
  <header class="crm-header">
    <div><p class="crm-kicker">CRM</p><h1>Клиенты</h1></div>
    <a href="#" class="crm-add-btn">+</a>
  </header>
  <div class="crm-stats">
    <div class="crm-stat tone-purple"><span class="crm-stat-icon">👥</span><div><strong>248</strong><span>клиентов</span></div></div>
    <div class="crm-stat tone-blue"><span class="crm-stat-icon">✦</span><div><strong>12</strong><span>новых</span></div></div>
  </div>
  <form class="crm-search"><input placeholder="Поиск клиентов…"></form>
  <nav class="crm-filters scrollable-x">
    <a href="#" class="crm-filter active">Все <em>248</em></a>
    <a href="#" class="crm-filter tone-green">Записан <em>18</em></a>
    <a href="#" class="crm-filter tone-orange">Думает <em>7</em></a>
    <a href="#" class="crm-filter tone-red">Отказ <em>4</em></a>
  </nav>
  <div class="crm-list">
    <a class="crm-card tone-green" href="#">
      <div class="crm-card-avatar">АК</div>
      <div class="crm-card-body">
        <div class="crm-card-top"><b>Алексей К.</b><span class="crm-card-date">19.06 14:00</span></div>
        <span class="crm-card-phone">+7 900 777-88-99</span>
        <span class="crm-card-car">Audi A6 · С789МН77</span>
        <span class="crm-pill tone-green">Записан</span>
      </div>
      <strong class="crm-card-price">5 500 ₽</strong>
    </a>
    <a class="crm-card tone-orange" href="#">
      <div class="crm-card-avatar">МС</div>
      <div class="crm-card-body">
        <div class="crm-card-top"><b>Мария Сидорова</b><span class="crm-card-date">18.06 16:20</span></div>
        <span class="crm-card-phone">+7 900 444-55-66</span>
        <span class="crm-card-car">Mercedes E · В456КХ99</span>
        <span class="crm-pill tone-orange">Думает</span>
      </div>
      <strong class="crm-card-price">6 000 ₽</strong>
    </a>
    <a class="crm-card tone-purple" href="#">
      <div class="crm-card-avatar">ИП</div>
      <div class="crm-card-body">
        <div class="crm-card-top"><b>Иван Петров</b><span class="crm-card-date">17.06 10:00</span></div>
        <span class="crm-card-phone">+7 900 111-22-33</span>
        <span class="crm-card-car">BMW X5 · А123ВС77</span>
        <span class="crm-pill tone-purple">Постоянный</span>
      </div>
      <strong class="crm-card-price">2 500 ₽</strong>
    </a>
  </div>
</div>
""",
    },
    "close": {
        "title": "Закрытие записи",
        "ribbon": "Закрытие · мастера, материалы, итог",
        "body": """
<div class="close-page">
  <header class="close-header">
    <a href="/design/preview/calendar" class="close-back">‹</a>
    <div><h1>Закрытие записи</h1><p>№42 · 19 июня · 14:00</p></div>
  </header>
  <div class="close-client card-surface">
    <div class="close-client-avatar">АК</div>
    <div class="close-client-body">
      <b>Алексей К.</b><span>+7 900 777-88-99</span><span>Audi A6 · С789МН77</span>
      <span class="close-service">Тонировка задней части</span>
    </div>
    <strong class="close-client-price">5 500 ₽</strong>
  </div>
  <form class="close-form">
    <section class="close-section card-surface">
      <h2>Мастера</h2>
      <div class="master-chips">
        <span class="master-chip">Стас <button type="button" class="master-chip-remove">×</button></span>
      </div>
    </section>
    <section class="close-section card-surface">
      <h2>Материалы</h2>
      <div class="material-rows close-material-rows">
        <div class="material-row close-material-row">
          <select><option>LLumar ATC 5% — 12.4 м²</option></select>
          <input placeholder="Длина, м" value="3.2">
          <input placeholder="Ширина, см" value="150">
          <button type="button" class="close-line-del">×</button>
        </div>
      </div>
      <button type="button" class="close-link-btn">+ Добавить материал</button>
    </section>
    <div class="close-summary card-surface">
      <div class="close-summary-item tone-blue"><span>Услуга</span><input class="close-price-input" value="5500"></div>
      <div class="close-summary-item tone-blue"><span>Расходники</span><strong>840 ₽</strong></div>
      <div class="close-summary-item tone-green"><span>Итого</span><strong>6 340 ₽</strong></div>
    </div>
    <button type="button" class="close-submit">Закрыть запись и сохранить ✓</button>
  </form>
</div>
""",
    },
    "analytics": {
        "title": "Аналитика",
        "ribbon": "Статистика · выручка, мастера, метрики",
        "body": """
<div class="an-page">
  <header class="an-header">
    <div><p class="an-kicker">Отчёты</p><h1>Аналитика</h1><p class="an-sub">19 июня 2026</p></div>
    <a href="#" class="an-cal-btn">📅</a>
  </header>
  <nav class="an-periods scrollable-x">
    <a href="#" class="an-period active">Сегодня</a>
    <a href="#" class="an-period">Неделя</a>
    <a href="#" class="an-period">Месяц</a>
  </nav>
  <div class="an-hero">
    <div class="an-hero-card tone-green"><span>Выручка</span><strong>48 200 ₽</strong><em class="up">12%</em></div>
    <div class="an-hero-card tone-purple"><span>Записей</span><strong>6</strong><em class="up">2%</em></div>
  </div>
  <section class="an-section card-surface">
    <h2>Выручка по мастерам</h2>
    <div class="an-bars">
      <div class="an-bar-row">
        <div class="an-bar-head"><span class="an-bar-avatar tone-green">К</span><b>Катя</b><strong>26 100 ₽</strong></div>
        <div class="an-bar-track"><i class="tone-green" style="width:72%"></i></div>
      </div>
      <div class="an-bar-row">
        <div class="an-bar-head"><span class="an-bar-avatar tone-blue">С</span><b>Стас</b><strong>22 100 ₽</strong></div>
        <div class="an-bar-track"><i class="tone-blue" style="width:61%"></i></div>
      </div>
    </div>
  </section>
  <div class="an-metrics">
    <div class="an-metric card-surface"><span>Средний чек</span><strong>8 033 ₽</strong><em class="up">5%</em></div>
    <div class="an-metric card-surface"><span>Конверсия</span><strong>68%</strong><em class="down">3%</em></div>
    <div class="an-metric card-surface"><span>Новые клиенты</span><strong>2</strong><em class="up">1</em></div>
    <div class="an-metric card-surface"><span>Отмены</span><strong>1</strong><em class="up">0%</em></div>
  </div>
</div>
""",
    },
    "employees": {
        "title": "Сотрудники",
        "ribbon": "Команда · роли, онлайн-запись, услуги",
        "body": """
<div class="emp-page">
  <header class="emp-header">
    <div><p class="emp-kicker">Команда</p><h1>Сотрудники</h1></div>
    <a href="#" class="emp-add-btn">+</a>
  </header>
  <form class="emp-search"><input placeholder="Поиск сотрудника…"></form>
  <nav class="emp-filters scrollable-x">
    <a href="#" class="emp-filter active">Все <em>5</em></a>
    <a href="#" class="emp-filter tone-green">Мастера <em>3</em></a>
    <a href="#" class="emp-filter tone-blue">Админы <em>1</em></a>
  </nav>
  <div class="emp-list">
    <article class="emp-card card-surface">
      <div class="emp-card-main">
        <div class="emp-avatar tone-green">К</div>
        <div class="emp-card-body">
          <div class="emp-card-top"><b>Катя</b><span class="emp-pill tone-green">Мастер</span></div>
          <span class="emp-meta">2 года · 412 закрытых</span>
          <span class="emp-login">@katya</span>
          <div class="emp-tags"><span class="emp-tag">Тонировка</span><span class="emp-tag">Атермальная</span></div>
        </div>
        <div class="emp-card-actions">
          <label class="emp-toggle"><span>Онлайн</span><input type="checkbox" checked><i></i></label>
        </div>
      </div>
    </article>
    <article class="emp-card card-surface">
      <div class="emp-card-main">
        <div class="emp-avatar tone-blue">С</div>
        <div class="emp-card-body">
          <div class="emp-card-top"><b>Стас</b><span class="emp-pill tone-blue">Мастер</span></div>
          <span class="emp-meta">3 года · 528 закрытых</span>
          <span class="emp-login">@stas</span>
          <div class="emp-tags"><span class="emp-tag">Тонировка</span></div>
        </div>
        <div class="emp-card-actions">
          <label class="emp-toggle"><span>Онлайн</span><input type="checkbox" checked><i></i></label>
        </div>
      </div>
    </article>
  </div>
</div>
""",
    },
    "stock": {
        "title": "Склад",
        "ribbon": "Склад · предложение: тёмные карточки как в CRM",
        "body": """
<div class="stk-page">
  <header class="stk-header">
    <div><p class="stk-kicker">Материалы</p><h1>Склад</h1></div>
    <a href="#" class="stk-add-btn">+</a>
  </header>
  <div class="stk-stats">
    <div class="stk-stat tone-green"><span>🎞</span><div><strong>8</strong><span>плёнок</span></div></div>
    <div class="stk-stat tone-orange"><span>⚠</span><div><strong>2</strong><span>мало</span></div></div>
    <div class="stk-stat tone-blue"><span>🔧</span><div><strong>14</strong><span>расходников</span></div></div>
  </div>
  <form class="stk-search"><input placeholder="Поиск по названию…"></form>
  <nav class="stk-filters scrollable-x">
    <a href="#" class="stk-filter active">Плёнка</a>
    <a href="#" class="stk-filter">Инструмент</a>
    <a href="#" class="stk-filter">Расходники</a>
  </nav>
  <div class="stk-grid">
    <article class="stk-card card-surface">
      <div class="stk-card-photo"><div class="stock-card-placeholder">🎞</div></div>
      <div class="stk-card-body">
        <div class="stk-card-top"><b>LLumar ATC 5%</b><strong>12,4 м²</strong></div>
        <div class="stock-bar-wrap"><div class="stock-bar stock-bar-mid" style="width:42%"></div></div>
        <span class="stk-meta">1,52 м · 420 ₽/м</span>
        <span class="stk-pill tone-orange">Средний остаток</span>
      </div>
    </article>
    <article class="stk-card card-surface">
      <div class="stk-card-photo"><div class="stock-card-placeholder">🎞</div></div>
      <div class="stk-card-body">
        <div class="stk-card-top"><b>SunTek CXP 15%</b><strong>3,1 м²</strong></div>
        <div class="stock-bar-wrap"><div class="stock-bar stock-bar-low" style="width:18%"></div></div>
        <span class="stk-meta">1,52 м · 380 ₽/м</span>
        <span class="stk-pill tone-red">Мало</span>
      </div>
    </article>
    <article class="stk-card card-surface">
      <div class="stk-card-photo"><div class="stock-card-placeholder">🧴</div></div>
      <div class="stk-card-body">
        <div class="stk-card-top"><b>Мыльный раствор</b><strong>6 шт</strong></div>
        <div class="stock-bar-wrap"><div class="stock-bar stock-bar-high" style="width:78%"></div></div>
        <span class="stk-meta">Расходник</span>
        <span class="stk-pill tone-green">В норме</span>
      </div>
    </article>
  </div>
</div>
""",
    },
}


def nav_class(key: str, active: str) -> str:
    return "active" if key == active else ""


def bn_class(key: str, active: str) -> str:
    return " active" if key == active else ""


def render_page(slug: str, meta: dict) -> str:
    nav_keys = ["dashboard", "calendar", "crm", "stock", "analytics", "employees", "close"]
    nav_map = {f"nav_{k}": nav_class(k, slug) for k in nav_keys}
    bn_map = {
        "bn_dashboard": bn_class("dashboard", slug),
        "bn_calendar": bn_class("calendar", slug),
        "bn_crm": bn_class("crm", slug),
        "bn_analytics": bn_class("analytics", slug),
    }
    head = SHELL_HEAD.format(title=meta["title"], ribbon=meta["ribbon"], **nav_map)
    foot = SHELL_FOOT.format(**bn_map)
    return head + meta["body"] + foot


def main():
    for slug, meta in PAGES.items():
        path = OUT / f"{slug}.html"
        path.write_text(render_page(slug, meta), encoding="utf-8")
        print("wrote", path)


if __name__ == "__main__":
    main()
