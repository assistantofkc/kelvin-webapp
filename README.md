# Kelvin's Personal Webapp 🌐

**Live Demo**: https://assistantofkc.pythonanywhere.com

---

## 📚 Apps 總覽

呢個係 Kelvin 嘅個人網頁項目，包含多個有用嘅工具：

### 1. 首頁 (/)
- Kelvin 嘅個人 landing page
- Profile: "Vibe Coder | AI Enthusiast"
- Bio: Hong Kong person who writes programs through vibe coding
- Social links: GitHub, LinkedIn, Email

### 2. 中文詞彙測試 (/vocab-test)
- AI -powered 中文詞彙測驗工具
- 輸入詞彙 → AI 自動生成填空題
- 批次式題目（每批 4 題）
- 支援多批次、累積分數
- 繁體中文句子生成
- 4 個選擇題（1 正確 + 3 干擾）

### 3. News Clipper (/news-clipper)
- 香港新聞文章解析工具
- 支援星島日報格式文章
- 自動擷取標題、來源、日期、內容
- 100% 客户端處理

### 4. Slide Translator
- Google Gemini app（外部連結）
- 投影片翻譯工具
- URL: https://gemini.google.com/share/34f6ac96cbc9

### 5. 倉頡學堂 (/cangjie)
- 倉頡輸入法練習工具
- 三個難度級別（Level 1-3）
- 互動式鍵盤練習
- 鍵位對照表 popup

---

## 🛠️ 技術架構

- **Frontend**: HTML5 + CSS3 + JavaScript (Vanilla)
- **Backend**: Flask (Python)
- **Hosting**: PythonAnywhere (Beginner tier)
- **AI API**: MiniMax-M2.7
- **React**: News Clipper (CDN)

---

## 📁 文件結構

```
kelvin-webapp/
├── app.py                      # Flask 後端
├── requirements.txt            # Python 依賴
├── .env                        # API keys (PythonAnywhere only - NOT in GitHub!)
├── .gitignore                  # 排除敏感檔案
├── .github/
│   └── workflows/
│       └── reload-pythonanywhere.yml  # 自動部署 workflow
├── templates/
│   ├── index.html              # 首頁
│   ├── vocab_test.html          # 中文詞彙測試
│   ├── news-clipper.html         # News Clipper
│   └── cangjie.html             # 倉頡學堂
└── static/
    ├── cangjie_keyboard_chart.jpg  # 倉頡鍵位對照圖
    └── ... other static assets
```

---

## 🚀 部署

### 自動部署（已設置 GitHub Actions）
1. Push to `main` branch
2. GitHub Action 自動 reload PythonAnywhere ✅

### 手動部署（如有問題）
```bash
# 在 PythonAnywhere Console 執行：
cd /home/assistantofkc/kelvin-webapp
git reset --hard origin/main
git pull origin main
```

---

## 🔒 安全說明

- `.env` 檔案包含敏感 API keys，**永不推送**到 GitHub
- MiniMax API key 只存在於 PythonAnywhere
- GitHub Secrets 用於 GitHub Actions

---

## 📝 版本歷史

| 版本 | 日期 | 更新內容 |
|-----|------|---------|
| v6.21 | 2026-04-23 | GitHub Action 自動部署 |
| v6.20 | 2026-04-23 | 倉頡鍵位圖片 popup |
| v6.19 | 2026-04-23 | Level 3 倉頡碼更新（支援5個鍵位）|

---

## 👤 作者

**Kelvin** - Vibe Coder | AI Enthusiast

- GitHub: https://github.com/assistantofkc
- LinkedIn: (見首頁)

---

*Last Updated: 2026-04-23*
