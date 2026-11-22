"""The News page's own text in every language the client has a newsletter URL for (served_gamedata.NEWSLETTER_LANGUAGES):
one table, MESSAGES (message id -> BCP 47 tag -> text), every id in every language with the same placeholders. That
includes the formats (weekday names, date / time order, duration units, list separator, label colon), so the page has
no per-language code: news.Texts formats everything from here. `problems()` checks the table; it is a startup content
check (startup.content_checks) and a test.

Content texts (event names, descriptions, rewards) come from the content set's localization instead
(news.Texts.loc): the language's Loc_<Language>.txt when the set has it, otherwise English.

Translations: the mode names come from the user's localization (Loc files) at run time; this table's own texts use
plain descriptive names.
"""

from __future__ import annotations

import string

# GameLanguage (the client's enum; Loc_<Language>.txt) -> BCP 47 tag (html lang, Intl date formats)
LANGUAGES: dict[str, str] = {
    "English": "en", "French": "fr", "German": "de", "Italian": "it", "Japanese": "ja", "Korean": "ko",
    "Russian": "ru", "Spanish": "es", "ChineseSimplified": "zh-Hans", "ChineseTraditional": "zh-Hant",
    "PortugueseBrazilian": "pt-BR",
}

M = dict[str, str]

MESSAGES: dict[str, M] = {
    # --- page chrome ---
    "title": {"en": "News", "fr": "Actualités", "de": "Neuigkeiten", "it": "Notizie", "ja": "お知らせ", "ko": "소식",
              "ru": "Новости", "es": "Noticias", "zh-Hans": "最新消息", "zh-Hant": "最新消息", "pt-BR": "Notícias"},
    "updated": {"en": "As of", "fr": "Mis à jour", "de": "Stand", "it": "Aggiornato al", "ja": "更新", "ko": "업데이트",
                "ru": "Обновлено", "es": "Actualizado", "zh-Hans": "更新时间", "zh-Hant": "更新時間",
                "pt-BR": "Atualizado em"},
    "now": {"en": "Now", "fr": "En cours", "de": "Läuft gerade", "it": "In corso", "ja": "開催中", "ko": "진행 중",
            "ru": "Сейчас", "es": "En curso", "zh-Hans": "进行中", "zh-Hant": "進行中", "pt-BR": "Agora"},
    "coming_up": {"en": "Coming up", "fr": "À venir", "de": "Demnächst", "it": "In arrivo", "ja": "開催予定",
                  "ko": "예정", "ru": "Скоро", "es": "Próximamente", "zh-Hans": "即将开始", "zh-Hant": "即將開始",
                  "pt-BR": "Em breve"},
    "soon": {"en": "Starting in the next 48 h", "fr": "Commence dans les 48 h", "de": "Beginnt in den nächsten 48 Std.",
             "it": "Inizia nelle prossime 48 h", "ja": "48時間以内に開始", "ko": "48시간 이내 시작",
             "ru": "Начнётся в ближайшие 48 ч", "es": "Empieza en las próximas 48 h", "zh-Hans": "48 小时内开始",
             "zh-Hant": "48 小時內開始", "pt-BR": "Começa nas próximas 48 h"},
    "week": {"en": "Next 7 days", "fr": "7 prochains jours", "de": "Nächste 7 Tage", "it": "Prossimi 7 giorni",
             "ja": "今後7日間", "ko": "향후 7일", "ru": "Ближайшие 7 дней", "es": "Próximos 7 días",
             "zh-Hans": "未来 7 天", "zh-Hant": "未來 7 天", "pt-BR": "Próximos 7 dias"},
    "always": {"en": "Always open", "fr": "Toujours ouvert", "de": "Immer verfügbar", "it": "Sempre disponibile",
               "ja": "常設", "ko": "상시 개방", "ru": "Всегда открыто", "es": "Siempre disponible",
               "zh-Hans": "常驻开放", "zh-Hant": "常駐開放", "pt-BR": "Sempre aberto"},
    "nothing": {"en": "Nothing scheduled.", "fr": "Rien de prévu.", "de": "Nichts geplant.",
                "it": "Niente in programma.", "ja": "予定はありません。", "ko": "예정된 일정이 없습니다.",
                "ru": "Ничего не запланировано.", "es": "No hay nada programado.", "zh-Hans": "目前没有安排。",
                "zh-Hant": "目前沒有排程。", "pt-BR": "Nada programado."},
    "empty_tab": {"en": "Nothing running or coming up here right now.",
                  "fr": "Rien en cours ni à venir ici pour le moment.",
                  "de": "Hier läuft gerade nichts, und es steht nichts an.",
                  "it": "Al momento qui non c'è niente in corso o in arrivo.",
                  "ja": "現在、開催中・開催予定のものはありません。", "ko": "지금은 진행 중이거나 예정된 항목이 없습니다.",
                  "ru": "Здесь сейчас ничего не идёт и ничего не запланировано.",
                  "es": "Ahora mismo no hay nada en curso ni próximo aquí.",
                  "zh-Hans": "这里目前没有进行中或即将开始的项目。", "zh-Hant": "這裡目前沒有進行中或即將開始的項目。",
                  "pt-BR": "Nada em andamento ou programado aqui no momento."},
    "ends_in": {"en": "Ends in", "fr": "Se termine dans", "de": "Endet in", "it": "Termina tra", "ja": "終了まで",
                "ko": "종료까지", "ru": "До конца", "es": "Termina en", "zh-Hans": "剩余", "zh-Hant": "剩餘",
                "pt-BR": "Termina em"},
    "starts_in": {"en": "Starts in", "fr": "Commence dans", "de": "Beginnt in", "it": "Inizia tra", "ja": "開始まで",
                  "ko": "시작까지", "ru": "До начала", "es": "Empieza en", "zh-Hans": "开始倒计时",
                  "zh-Hant": "開始倒數", "pt-BR": "Começa em"},
    "ended": {"en": "Ended", "fr": "Terminé", "de": "Beendet", "it": "Terminato", "ja": "終了", "ko": "종료됨",
              "ru": "Завершено", "es": "Terminado", "zh-Hans": "已结束", "zh-Hant": "已結束", "pt-BR": "Encerrado"},
    "rewards": {"en": "Rewards", "fr": "Récompenses", "de": "Belohnungen", "it": "Ricompense", "ja": "報酬",
                "ko": "보상", "ru": "Награды", "es": "Recompensas", "zh-Hans": "奖励", "zh-Hant": "獎勵",
                "pt-BR": "Recompensas"},
    "more": {"en": "Details", "fr": "Détails", "de": "Details", "it": "Dettagli", "ja": "詳細", "ko": "자세히",
             "ru": "Подробнее", "es": "Detalles", "zh-Hans": "详细内容", "zh-Hant": "詳細內容", "pt-BR": "Detalhes"},
    "go": {"en": "Go", "fr": "Y aller", "de": "Los", "it": "Vai", "ja": "移動", "ko": "이동", "ru": "Перейти",
           "es": "Ir", "zh-Hans": "前往", "zh-Hant": "前往", "pt-BR": "Ir"},
    "tiers": {"en": "Tiers cleared: {done}/{total}", "fr": "Paliers terminés : {done}/{total}",
              "de": "Abgeschlossene Stufen: {done}/{total}", "it": "Fasi completate: {done}/{total}",
              "ja": "クリア済みティア：{done}/{total}", "ko": "클리어한 단계: {done}/{total}",
              "ru": "Пройдено этапов: {done}/{total}", "es": "Fases superadas: {done}/{total}",
              "zh-Hans": "已通关阶层：{done}/{total}", "zh-Hant": "已通關階層：{done}/{total}",
              "pt-BR": "Fases concluídas: {done}/{total}"},
    "unlocks": {"en": "Unlocks at level {level}", "fr": "Débloqué au niveau {level}",
                "de": "Freigeschaltet ab Level {level}", "it": "Si sblocca al livello {level}",
                "ja": "レベル{level}で解放", "ko": "레벨 {level}에 잠금 해제", "ru": "Откроется на уровне {level}",
                "es": "Se desbloquea en el nivel {level}", "zh-Hans": "于等级{level}解锁",
                "zh-Hant": "於等級{level}解鎖", "pt-BR": "Desbloqueia no nível {level}"},
    # --- tabs (news.TABS) ---
    "tab_overview": {"en": "Overview", "fr": "Aperçu", "de": "Übersicht", "it": "Panoramica", "ja": "概要",
                     "ko": "개요", "ru": "Обзор", "es": "Resumen", "zh-Hans": "总览", "zh-Hant": "總覽",
                     "pt-BR": "Visão geral"},
    "tab_events": {"en": "Events", "fr": "Événements", "de": "Events", "it": "Eventi", "ja": "イベント",
                   "ko": "이벤트", "ru": "События", "es": "Eventos", "zh-Hans": "活动", "zh-Hant": "活動",
                   "pt-BR": "Eventos"},
    "tab_pvp": {"en": "PvP", "fr": "JcJ", "de": "PvP", "it": "PvP", "ja": "PvP", "ko": "PvP", "ru": "PvP",
                "es": "JcJ", "zh-Hans": "对战", "zh-Hant": "對戰", "pt-BR": "PvP"},
    "tab_clubs": {"en": "Clubs", "fr": "Clubs", "de": "Clubs", "it": "Club", "ja": "クラブ", "ko": "클럽",
                  "ru": "Клубы", "es": "Clubes", "zh-Hans": "社团", "zh-Hant": "社團", "pt-BR": "Clubes"},
    "tab_rewards": {"en": "Rewards & Store", "fr": "Récompenses et boutique", "de": "Belohnungen & Shop",
                    "it": "Ricompense e negozio", "ja": "報酬・ショップ", "ko": "보상 및 상점", "ru": "Награды и магазин",
                    "es": "Recompensas y tienda", "zh-Hans": "奖励与商店", "zh-Hant": "獎勵與商店",
                    "pt-BR": "Recompensas e loja"},
    "tab_how": {"en": "How it works", "fr": "Fonctionnement", "de": "So funktioniert's", "it": "Come funziona",
                "ja": "仕組み", "ko": "진행 방식", "ru": "Как это работает", "es": "Cómo funciona",
                "zh-Hans": "日程说明", "zh-Hant": "排程說明", "pt-BR": "Como funciona"},
    # --- kinds (schedule.KINDS) ---
    "event": {"en": "Event", "fr": "Événement", "de": "Event", "it": "Evento", "ja": "イベント", "ko": "이벤트",
              "ru": "Событие", "es": "Evento", "zh-Hans": "活动", "zh-Hant": "活動", "pt-BR": "Evento"},
    "trial": {"en": "Sorcerer's Trial", "fr": "Épreuve du sorcier", "de": "Zauberer-Prüfung",
              "it": "Prova dello stregone", "ja": "ソーサラーの試練", "ko": "소서러의 시련", "ru": "Испытание чародея",
              "es": "Prueba del hechicero", "zh-Hans": "魔法师试炼", "zh-Hant": "魔法師試煉",
              "pt-BR": "Prova do feiticeiro"},
    "tower": {"en": "Tower Event", "fr": "Événement de la tour", "de": "Turm-Event", "it": "Evento torre",
              "ja": "タワーイベント", "ko": "타워 이벤트", "ru": "Событие «Башня»", "es": "Evento de torre",
              "zh-Hans": "活动塔楼", "zh-Hant": "活動塔樓", "pt-BR": "Evento da torre"},
    "contest": {"en": "Leaderboard Contest", "fr": "Concours de classement", "de": "Ranglisten-Wettbewerb",
                "it": "Gara in classifica", "ja": "ランキングコンテスト", "ko": "순위표 대회",
                "ru": "Рейтинговое состязание", "es": "Concurso de clasificación", "zh-Hans": "排行榜竞赛",
                "zh-Hant": "排行榜競賽", "pt-BR": "Competição de ranking"},
    "showdown": {"en": "Summoner Showdown", "fr": "Duel des invocateurs", "de": "Beschwörer-Showdown",
                 "it": "Sfida degli evocatori", "ja": "サモナーショーダウン", "ko": "소환사 쇼다운",
                 "ru": "Схватка призывателей", "es": "Duelo de invocadores", "zh-Hans": "召唤者对决",
                 "zh-Hant": "召喚者對決", "pt-BR": "Duelo de invocadores"},
    "passport": {"en": "Passholder Season", "fr": "Saison du passe", "de": "Pass-Saison", "it": "Stagione del pass",
                 "ja": "パスシーズン", "ko": "패스 시즌", "ru": "Сезон пропуска", "es": "Temporada del pase",
                 "zh-Hans": "护照玩家赛季", "zh-Hant": "護照玩家賽季", "pt-BR": "Temporada do passe"},
    "pvp": {"en": "PvP Arena season", "fr": "Saison de l'arène JcJ", "de": "PvP-Arena-Saison",
            "it": "Stagione dell'arena PvP", "ja": "PvPアリーナシーズン", "ko": "PvP 아레나 시즌",
            "ru": "Сезон PvP-арены", "es": "Temporada de la arena JcJ", "zh-Hans": "PvP 竞技场赛季",
            "zh-Hant": "PvP 競技場賽季", "pt-BR": "Temporada da arena PvP"},
    "club_war": {"en": "Club Conquest", "fr": "Conquête de clubs", "de": "Club-Eroberung", "it": "Conquista dei club",
                 "ja": "クラブ征服戦", "ko": "클럽 정복전", "ru": "Завоевание клубов", "es": "Conquista de clubes",
                 "zh-Hans": "社团征服战", "zh-Hant": "社團征服戰", "pt-BR": "Conquista de clubes"},
    "expedition": {"en": "Club Expedition", "fr": "Expédition de club", "de": "Club-Expedition",
                   "it": "Spedizione del club", "ja": "クラブ遠征", "ko": "클럽 원정", "ru": "Экспедиция клуба",
                   "es": "Expedición de club", "zh-Hans": "社团远征", "zh-Hant": "社團遠征",
                   "pt-BR": "Expedição do clube"},
    "festival": {"en": "Festival store", "fr": "Boutique du festival", "de": "Festival-Shop",
                 "it": "Negozio del festival", "ja": "フェスティバルショップ", "ko": "축제 상점",
                 "ru": "Магазин фестиваля", "es": "Tienda del festival", "zh-Hans": "节庆商店", "zh-Hant": "節慶商店",
                 "pt-BR": "Loja do festival"},
    "festival_bonus": {"en": "Expedition festival bonus", "fr": "Bonus de festival des expéditions",
                       "de": "Expeditions-Festivalbonus", "it": "Bonus festival delle spedizioni",
                       "ja": "遠征フェスティバルボーナス", "ko": "원정 축제 보너스", "ru": "Бонус фестиваля экспедиций",
                       "es": "Bonificación de festival de expediciones", "zh-Hans": "社团远征节庆红利",
                       "zh-Hant": "社團遠征節慶紅利", "pt-BR": "Bônus de festival das expedições"},
    "flash_gift": {"en": "Flash Gifts", "fr": "Cadeaux éclair", "de": "Blitzgeschenke", "it": "Regali lampo",
                   "ja": "フラッシュギフト", "ko": "반짝 선물", "ru": "Мгновенные подарки", "es": "Regalos relámpago",
                   "zh-Hans": "限时礼物", "zh-Hant": "限時禮物", "pt-BR": "Presentes relâmpago"},
    "special_offer": {"en": "Special Offer", "fr": "Offre spéciale", "de": "Sonderangebot", "it": "Offerta speciale",
                      "ja": "特別オファー", "ko": "특별 할인", "ru": "Специальное предложение", "es": "Oferta especial",
                      "zh-Hans": "特别优惠", "zh-Hant": "特別優惠", "pt-BR": "Oferta especial"},
    "mystic_leap": {"en": "Mystic Leap", "fr": "Bond mystique", "de": "Mystischer Sprung", "it": "Salto mistico",
                    "ja": "ミスティックリープ", "ko": "미스틱 리프", "ru": "Мистический прыжок", "es": "Salto místico",
                    "zh-Hans": "神秘飞跃", "zh-Hant": "神秘飛躍", "pt-BR": "Salto místico"},
    "login_calendar": {"en": "Login Calendar", "fr": "Calendrier de connexion", "de": "Login-Kalender",
                       "it": "Calendario di accesso", "ja": "ログインカレンダー", "ko": "로그인 캘린더",
                       "ru": "Календарь входа", "es": "Calendario de inicio de sesión", "zh-Hans": "登录日历",
                       "zh-Hant": "登入日曆", "pt-BR": "Calendário de login"},
    "stamp_card": {"en": "Stamp Card", "fr": "Carte à tampons", "de": "Stempelkarte", "it": "Carta timbri",
                   "ja": "スタンプカード", "ko": "스탬프 카드", "ru": "Карта штампов", "es": "Tarjeta de sellos",
                   "zh-Hans": "集章卡", "zh-Hant": "集章卡", "pt-BR": "Cartão de selos"},
    "bonus_loot": {"en": "Bonus Loot", "fr": "Butin bonus", "de": "Bonus-Beute", "it": "Bottino bonus",
                   "ja": "ボーナス戦利品", "ko": "보너스 전리품", "ru": "Бонусная добыча", "es": "Botín extra",
                   "zh-Hans": "红利战利品", "zh-Hant": "紅利戰利品", "pt-BR": "Saque bônus"},
    "daily": {"en": "Summoner Challenges", "fr": "Défis de l'invocateur", "de": "Beschwörer-Herausforderungen",
              "it": "Sfide dell'evocatore", "ja": "サモナーチャレンジ", "ko": "소환사 도전", "ru": "Испытания призывателя",
              "es": "Desafíos del invocador", "zh-Hans": "召唤者挑战", "zh-Hant": "召喚者挑戰",
              "pt-BR": "Desafios do invocador"},
    "koth": {"en": "Sorcerer's Tournament payout", "fr": "Récompenses du tournoi des sorciers",
             "de": "Zauberer-Turnier-Auszahlung", "it": "Premi del torneo degli stregoni",
             "ja": "ソーサラートーナメント報酬", "ko": "소서러 토너먼트 보상", "ru": "Награды турнира чародеев",
             "es": "Premios del torneo de hechiceros", "zh-Hans": "魔法师锦标赛发奖", "zh-Hant": "魔法師錦標賽發獎",
             "pt-BR": "Prêmios do torneio de feiticeiros"},
    "raid": {"en": "Raid", "fr": "Raid", "de": "Raid", "it": "Raid", "ja": "レイド", "ko": "레이드", "ru": "Рейд",
             "es": "Incursión", "zh-Hans": "突袭", "zh-Hant": "突襲", "pt-BR": "Raide"},
    "permanent_event": {"en": "One-time event", "fr": "Événement unique", "de": "Einmaliges Event",
                        "it": "Evento unico", "ja": "一回限りのイベント", "ko": "일회성 이벤트", "ru": "Разовое событие",
                        "es": "Evento único", "zh-Hans": "一次性活动", "zh-Hant": "一次性活動", "pt-BR": "Evento único"},
    # --- how it works (news.how_it_works) ---
    "speed": {
        "en": "The game runs at {speed}× real time: schedules, daily resets, energy, cooldowns and timers all run "
              "{speed} times faster (a game day is {day}); all dates are real dates on your device.",
        "fr": "Le jeu tourne à {speed}× le temps réel : calendriers, réinitialisations quotidiennes, énergie, temps de "
              "recharge et minuteurs vont tous {speed} fois plus vite (une journée de jeu dure {day}) ; toutes les "
              "dates sont les dates réelles de votre appareil.",
        "de": "Das Spiel läuft mit {speed}-facher Echtzeit: Zeitpläne, tägliche Resets, Energie, Abklingzeiten und "
              "Timer laufen alle {speed}-mal so schnell (ein Spieltag dauert {day}); alle Daten sind echte Daten auf "
              "deinem Gerät.",
        "it": "Il gioco scorre a {speed}× il tempo reale: calendari, reset giornalieri, energia, tempi di ricarica e "
              "timer vanno tutti {speed} volte più veloci (un giorno di gioco dura {day}); tutte le date sono quelle "
              "reali del tuo dispositivo.",
        "ja": "ゲームは実時間の{speed}倍の速さで進みます：スケジュール、デイリーリセット、エネルギー、クールダウン、"
              "各種タイマーがすべて{speed}倍速です（ゲーム内の1日は{day}）。日付はすべて端末上の実際の日付です。",
        "ko": "게임은 실제 시간의 {speed}배 속도로 진행됩니다: 일정, 일일 초기화, 에너지, 재사용 대기시간, 타이머가 "
              "모두 {speed}배 빠릅니다(게임의 하루는 {day}). 모든 날짜는 기기의 실제 날짜입니다.",
        "ru": "Игра идёт со скоростью {speed}× от реального времени: расписания, ежедневные сбросы, энергия, "
              "перезарядки и таймеры ускорены во столько же раз (игровые сутки длятся {day}); все даты — реальные "
              "даты на вашем устройстве.",
        "es": "El juego va a {speed}× el tiempo real: calendarios, reinicios diarios, energía, tiempos de recarga y "
              "temporizadores van {speed} veces más rápido (un día de juego dura {day}); todas las fechas son las "
              "reales de tu dispositivo.",
        "zh-Hans": "游戏以真实时间的 {speed} 倍运行：日程、每日重置、体力、冷却和各种计时都快 {speed} 倍（游戏的一天是 "
                   "{day}）；所有日期都是你设备上的真实日期。",
        "zh-Hant": "遊戲以真實時間的 {speed} 倍執行：排程、每日重置、體力、冷卻和各種計時都快 {speed} 倍（遊戲的一天是 "
                   "{day}）；所有日期都是你裝置上的真實日期。",
        "pt-BR": "O jogo roda a {speed}× o tempo real: programação, reinícios diários, energia, recargas e cronômetros "
                 "ficam todos {speed} vezes mais rápidos (um dia de jogo dura {day}); todas as datas são as datas "
                 "reais do seu aparelho.",
    },
    "daily_reset": {
        "en": "Daily reset (quests, purchase limits, energy gifts): every day at {time}.",
        "fr": "Réinitialisation quotidienne (quêtes, limites d'achat, cadeaux d'énergie) : tous les jours à {time}.",
        "de": "Täglicher Reset (Quests, Kauflimits, Energiegeschenke): jeden Tag um {time}.",
        "it": "Reset giornaliero (missioni, limiti di acquisto, regali di energia): ogni giorno alle {time}.",
        "ja": "デイリーリセット（クエスト、購入回数制限、エネルギーギフト）：毎日{time}。",
        "ko": "일일 초기화(퀘스트, 구매 한도, 에너지 선물): 매일 {time}.",
        "ru": "Ежедневный сброс (задания, лимиты покупок, подарки энергии): каждый день в {time}.",
        "es": "Reinicio diario (misiones, límites de compra, regalos de energía): todos los días a las {time}.",
        "zh-Hans": "每日重置（任务、购买次数、能量礼物）：每天 {time}。",
        "zh-Hant": "每日重置（任務、購買次數、能量禮物）：每天 {time}。",
        "pt-BR": "Reinício diário (missões, limites de compra, presentes de energia): todo dia às {time}.",
    },
    "daily_reset_next": {
        "en": "Next daily reset (quests, purchase limits, energy gifts): {time}.",
        "fr": "Prochaine réinitialisation quotidienne (quêtes, limites d'achat, cadeaux d'énergie) : {time}.",
        "de": "Nächster täglicher Reset (Quests, Kauflimits, Energiegeschenke): {time}.",
        "it": "Prossimo reset giornaliero (missioni, limiti di acquisto, regali di energia): {time}.",
        "ja": "次のデイリーリセット（クエスト、購入回数制限、エネルギーギフト）：{time}。",
        "ko": "다음 일일 초기화(퀘스트, 구매 한도, 에너지 선물): {time}.",
        "ru": "Следующий ежедневный сброс (задания, лимиты покупок, подарки энергии): {time}.",
        "es": "Próximo reinicio diario (misiones, límites de compra, regalos de energía): {time}.",
        "zh-Hans": "下次每日重置（任务、购买次数、能量礼物）：{time}。",
        "zh-Hant": "下次每日重置（任務、購買次數、能量禮物）：{time}。",
        "pt-BR": "Próximo reinício diário (missões, limites de compra, presentes de energia): {time}.",
    },
    "weekly_reset": {
        "en": "Free gem packs: once a week, reset Monday {time}.",
        "fr": "Packs de gemmes gratuits : une fois par semaine, réinitialisation le lundi à {time}.",
        "de": "Kostenlose Edelsteinpakete: einmal pro Woche, Reset montags um {time}.",
        "it": "Pacchetti di gemme gratuiti: una volta a settimana, reset il lunedì alle {time}.",
        "ja": "無料ジェムパック：週1回、毎週月曜{time}にリセット。",
        "ko": "무료 보석 팩: 주 1회, 월요일 {time}에 초기화.",
        "ru": "Бесплатные наборы самоцветов: раз в неделю, сброс в понедельник в {time}.",
        "es": "Packs de gemas gratis: una vez por semana, se reinicia el lunes a las {time}.",
        "zh-Hans": "免费宝石组合包：每周一次，周一 {time} 重置。",
        "zh-Hant": "免費寶石組合包：每週一次，週一 {time} 重置。",
        "pt-BR": "Pacotes de gemas grátis: uma vez por semana, reinício na segunda-feira às {time}.",
    },
    "weekly_reset_next": {
        "en": "Free gem packs: once a game week, next reset {time}.",
        "fr": "Packs de gemmes gratuits : une fois par semaine de jeu, prochaine réinitialisation {time}.",
        "de": "Kostenlose Edelsteinpakete: einmal pro Spielwoche, nächster Reset {time}.",
        "it": "Pacchetti di gemme gratuiti: una volta per settimana di gioco, prossimo reset {time}.",
        "ja": "無料ジェムパック：ゲーム内の週1回、次のリセットは{time}。",
        "ko": "무료 보석 팩: 게임 기준 주 1회, 다음 초기화 {time}.",
        "ru": "Бесплатные наборы самоцветов: раз в игровую неделю, следующий сброс {time}.",
        "es": "Packs de gemas gratis: una vez por semana de juego, próximo reinicio {time}.",
        "zh-Hans": "免费宝石组合包：游戏中每周一次，下次重置 {time}。",
        "zh-Hant": "免費寶石組合包：遊戲的每週一次，下次重置 {time}。",
        "pt-BR": "Pacotes de gemas grátis: uma vez por semana de jogo, próximo reinício {time}.",
    },
    "raid_refill": {
        "en": "Raids: attempts, heroes and spells refill every {interval}.",
        "fr": "Raids : tentatives, héros et sorts se rechargent (intervalle : {interval}).",
        "de": "Raids: Versuche, Helden und Zauber füllen sich wieder auf (Intervall: {interval}).",
        "it": "Raid: tentativi, eroi e incantesimi si ricaricano ogni {interval}.",
        "ja": "レイド：挑戦回数・ヒーロー・呪文は{interval}ごとに回復。",
        "ko": "레이드: 도전 횟수, 영웅, 주문이 {interval}마다 회복됩니다.",
        "ru": "Рейды: попытки, герои и заклинания восстанавливаются раз в {interval}.",
        "es": "Incursiones: los intentos, héroes y hechizos se recargan cada {interval}.",
        "zh-Hans": "突袭：挑战次数、英雄与法术每 {interval}恢复。",
        "zh-Hant": "突襲：挑戰次數、英雄與法術每 {interval}恢復。",
        "pt-BR": "Raides: tentativas, heróis e feitiços recarregam a cada {interval}.",
    },
    "raid_midnight": {
        "en": "Raids: attempts refill at midnight in the club leader's time zone.",
        "fr": "Raids : les tentatives se rechargent à minuit, heure du chef de club.",
        "de": "Raids: Versuche füllen sich um Mitternacht in der Zeitzone des Clubleiters wieder auf.",
        "it": "Raid: i tentativi si ricaricano a mezzanotte nel fuso orario del capo del club.",
        "ja": "レイド：挑戦回数はクラブリーダーのタイムゾーンの午前0時に回復。",
        "ko": "레이드: 도전 횟수는 클럽 리더 시간대의 자정에 회복됩니다.",
        "ru": "Рейды: попытки восстанавливаются в полночь по часовому поясу главы клуба.",
        "es": "Incursiones: los intentos se recargan a medianoche en la zona horaria del líder del club.",
        "zh-Hans": "突袭：挑战次数于社团会长时区的午夜恢复。",
        "zh-Hant": "突襲：挑戰次數於社團會長時區的午夜恢復。",
        "pt-BR": "Raides: as tentativas recarregam à meia-noite no fuso horário do líder do clube.",
    },
    "club_war_on": {
        "en": "Club Conquest: a war is always running for your club.",
        "fr": "Conquête de clubs : une guerre est toujours en cours pour votre club.",
        "de": "Club-Eroberung: Für deinen Club läuft immer ein Krieg.",
        "it": "Conquista dei club: per il tuo club c'è sempre una guerra in corso.",
        "ja": "クラブ征服戦：あなたのクラブでは常に征服戦が行われています。",
        "ko": "클럽 정복전: 클럽에서 항상 정복전이 진행 중입니다.",
        "ru": "Завоевание клубов: у вашего клуба всегда идёт война.",
        "es": "Conquista de clubes: tu club siempre tiene una guerra en curso.",
        "zh-Hans": "社团征服战：你的社团随时都有一场征服战进行中。",
        "zh-Hant": "社團征服戰：你的社團隨時都有一場征服戰進行中。",
        "pt-BR": "Conquista de clubes: sempre há uma guerra em andamento para o seu clube.",
    },
    "lta_closed": {
        "en": "Summoner Showdown: closed for the regroup phase each day until {time}.",
        "fr": "Duel des invocateurs : fermé chaque jour pendant la phase de regroupement jusqu'à {time}.",
        "de": "Beschwörer-Showdown: täglich während der Sammelphase geschlossen bis {time}.",
        "it": "Sfida degli evocatori: chiusa ogni giorno durante la fase di riorganizzazione fino alle {time}.",
        "ja": "サモナーショーダウン：毎日の再編成フェーズ中は{time}まで閉鎖。",
        "ko": "소환사 쇼다운: 매일 재편성 단계 동안 {time}까지 닫힙니다.",
        "ru": "Схватка призывателей: ежедневно закрыта на время перегруппировки до {time}.",
        "es": "Duelo de invocadores: cerrado cada día durante la fase de reagrupación hasta las {time}.",
        "zh-Hans": "召唤者对决：每天重整阶段关闭至 {time}。",
        "zh-Hant": "召喚者對決：每天重整階段關閉至 {time}。",
        "pt-BR": "Duelo de invocadores: fechado todo dia durante a fase de reagrupamento até {time}.",
    },
    "offers": {
        "en": "Special offers: {slots} on sale at once, each for {length}.",
        "fr": "Offres spéciales : {slots} en vente en même temps, chacune pendant {length}.",
        "de": "Sonderangebote: {slots} gleichzeitig im Angebot, jedes für {length}.",
        "it": "Offerte speciali: {slots} in vendita contemporaneamente, ciascuna per {length}.",
        "ja": "特別オファー：同時に{slots}件販売、各{length}。",
        "ko": "특별 할인: 동시에 {slots}개 판매, 각각 {length} 동안.",
        "ru": "Специальные предложения: одновременно в продаже — {slots}, каждое на {length}.",
        "es": "Ofertas especiales: {slots} a la venta a la vez, cada una durante {length}.",
        "zh-Hans": "特别优惠：同时销售 {slots} 项，每项 {length}。",
        "zh-Hant": "特別優惠：同時販售 {slots} 項，每項 {length}。",
        "pt-BR": "Ofertas especiais: {slots} à venda ao mesmo tempo, cada uma por {length}.",
    },
    "kind_rule": {"en": "{kind}: {days} · {length}", "fr": "{kind} : {days} · durée {length}",
                  "de": "{kind}: {days} · Dauer {length}", "it": "{kind}: {days} · durata {length}",
                  "ja": "{kind}：{days}・期間{length}", "ko": "{kind}: {days} · 기간 {length}",
                  "ru": "{kind}: {days} · длится {length}", "es": "{kind}: {days} · dura {length}",
                  "zh-Hans": "{kind}：{days} · 为期 {length}", "zh-Hant": "{kind}：{days} · 為期 {length}",
                  "pt-BR": "{kind}: {days} · dura {length}"},
    "every_n": {"en": "a new one every {gap}", "fr": "une nouvelle édition à intervalle de {gap}",
                "de": "ein neues im Abstand von {gap}", "it": "una nuova ogni {gap}", "ja": "{gap}ごとに新しく開始",
                "ko": "{gap}마다 새로 시작", "ru": "новое раз в {gap}", "es": "una nueva cada {gap}",
                "zh-Hans": "每 {gap} 一个新的", "zh-Hant": "每 {gap} 一個新的", "pt-BR": "uma nova a cada {gap}"},
    # --- formats ---
    # durations (how it works, countdowns): no plurals, the short unit forms
    "unit_d": {"en": "{n}d", "fr": "{n} j", "de": "{n} T.", "it": "{n} g", "ja": "{n}日", "ko": "{n}일", "ru": "{n} д",
               "es": "{n} d", "zh-Hans": "{n} 天", "zh-Hant": "{n} 天", "pt-BR": "{n} d"},
    "unit_h": {"en": "{n}h", "fr": "{n} h", "de": "{n} Std.", "it": "{n} h", "ja": "{n}時間", "ko": "{n}시간",
               "ru": "{n} ч", "es": "{n} h", "zh-Hans": "{n} 小时", "zh-Hant": "{n} 小時", "pt-BR": "{n} h"},
    "unit_m": {"en": "{n}m", "fr": "{n} min", "de": "{n} Min.", "it": "{n} min", "ja": "{n}分", "ko": "{n}분",
               "ru": "{n} мин", "es": "{n} min", "zh-Hans": "{n} 分", "zh-Hant": "{n} 分", "pt-BR": "{n} min"},
    "unit_s": {"en": "{n}s", "fr": "{n} s", "de": "{n} Sek.", "it": "{n} s", "ja": "{n}秒", "ko": "{n}초",
               "ru": "{n} с", "es": "{n} s", "zh-Hans": "{n} 秒", "zh-Hant": "{n} 秒", "pt-BR": "{n} s"},
    # weekday abbreviations, Monday = wd_0 (datetime.weekday())
    "wd_0": {"en": "Mon", "fr": "lun.", "de": "Mo.", "it": "lun", "ja": "月", "ko": "월", "ru": "пн", "es": "lun",
             "zh-Hans": "周一", "zh-Hant": "週一", "pt-BR": "seg"},
    "wd_1": {"en": "Tue", "fr": "mar.", "de": "Di.", "it": "mar", "ja": "火", "ko": "화", "ru": "вт", "es": "mar",
             "zh-Hans": "周二", "zh-Hant": "週二", "pt-BR": "ter"},
    "wd_2": {"en": "Wed", "fr": "mer.", "de": "Mi.", "it": "mer", "ja": "水", "ko": "수", "ru": "ср", "es": "mié",
             "zh-Hans": "周三", "zh-Hant": "週三", "pt-BR": "qua"},
    "wd_3": {"en": "Thu", "fr": "jeu.", "de": "Do.", "it": "gio", "ja": "木", "ko": "목", "ru": "чт", "es": "jue",
             "zh-Hans": "周四", "zh-Hant": "週四", "pt-BR": "qui"},
    "wd_4": {"en": "Fri", "fr": "ven.", "de": "Fr.", "it": "ven", "ja": "金", "ko": "금", "ru": "пт", "es": "vie",
             "zh-Hans": "周五", "zh-Hant": "週五", "pt-BR": "sex"},
    "wd_5": {"en": "Sat", "fr": "sam.", "de": "Sa.", "it": "sab", "ja": "土", "ko": "토", "ru": "сб", "es": "sáb",
             "zh-Hans": "周六", "zh-Hant": "週六", "pt-BR": "sáb"},
    "wd_6": {"en": "Sun", "fr": "dim.", "de": "So.", "it": "dom", "ja": "日", "ko": "일", "ru": "вс", "es": "dom",
             "zh-Hans": "周日", "zh-Hant": "週日", "pt-BR": "dom"},
    # day of the month: numeric, in the language's order ({m} / {d} without leading zeros); times are 24 h HH:MM
    "date": {"en": "{m}/{d}", "fr": "{d}/{m}", "de": "{d}.{m}.", "it": "{d}/{m}", "ja": "{m}/{d}", "ko": "{m}. {d}.",
             "ru": "{d}.{m}", "es": "{d}/{m}", "zh-Hans": "{m}/{d}", "zh-Hant": "{m}/{d}", "pt-BR": "{d}/{m}"},
    "datetime": {"en": "{wd} {date} {time}", "fr": "{wd} {date} {time}", "de": "{wd}, {date} {time}",
                 "it": "{wd} {date} {time}", "ja": "{date}({wd}) {time}", "ko": "{date} ({wd}) {time}",
                 "ru": "{wd}, {date} {time}", "es": "{wd} {date} {time}", "zh-Hans": "{wd} {date} {time}",
                 "zh-Hant": "{wd} {date} {time}", "pt-BR": "{wd}, {date} {time}"},
    "weekday_time": {"en": "{wd} {time}", "fr": "{wd} {time}", "de": "{wd} {time}", "it": "{wd} {time}",
                     "ja": "{wd}曜 {time}", "ko": "{wd}요일 {time}", "ru": "{wd} {time}", "es": "{wd} {time}",
                     "zh-Hans": "{wd} {time}", "zh-Hant": "{wd} {time}", "pt-BR": "{wd} {time}"},
    "label": {"en": "{label}:", "fr": "{label} :", "de": "{label}:", "it": "{label}:", "ja": "{label}：",
              "ko": "{label}:", "ru": "{label}:", "es": "{label}:", "zh-Hans": "{label}：", "zh-Hant": "{label}：",
              "pt-BR": "{label}:"},
    "list_sep": {"en": ", ", "fr": ", ", "de": ", ", "it": ", ", "ja": "、", "ko": ", ", "ru": ", ", "es": ", ",
                 "zh-Hans": "、", "zh-Hant": "、", "pt-BR": ", "},
}

# message ids that are formats (no words of their own): an untranslated-text check skips them
FORMATS = frozenset({"unit_d", "unit_h", "unit_m", "unit_s", "date", "datetime", "weekday_time", "label", "list_sep",
                     "kind_rule"})


def placeholders(text: str) -> frozenset[str]:
    return frozenset(f for _, f, _, _ in string.Formatter().parse(text) if f is not None)


def required_ids() -> set[str]:
    """Ids the page looks up by name pattern: one per schedule kind and per tab, the weekdays."""
    from arcane_server import news, schedule

    return {*schedule.KINDS, *(f"tab_{t}" for t in news.TABS), *(f"wd_{i}" for i in range(7))}


def problems() -> list[str]:
    """Everything wrong with the table: a language missing or empty, placeholders differing from English, an id
    the page needs missing, the language list not the client's newsletter languages."""
    from arcane_server import news
    from arcane_server.served_gamedata import NEWSLETTER_LANGUAGES

    out = []
    client = {news.loc_language(f) for f in NEWSLETTER_LANGUAGES}
    if set(LANGUAGES) != client:
        out.append(f"LANGUAGES {sorted(LANGUAGES)} != the client's newsletter languages {sorted(client)}")
    tags = set(LANGUAGES.values())
    for mid, texts in MESSAGES.items():
        if set(texts) != tags:
            out.append(f"{mid}: missing {sorted(tags - set(texts))}, unknown {sorted(set(texts) - tags)}")
        want = placeholders(texts.get("en", ""))
        for tag, text in texts.items():
            if not (text if mid == "list_sep" else text.strip()):  # (a separator may be just ", ")
                out.append(f"{mid} [{tag}]: empty")
            try:
                got = placeholders(text)
            except ValueError as e:
                out.append(f"{mid} [{tag}]: bad format ({e})")
                continue
            if got != want:
                out.append(f"{mid} [{tag}]: placeholders {sorted(got)} != English {sorted(want)}")
    out += [f"{mid}: no such message" for mid in sorted(required_ids() - set(MESSAGES))]
    return out
