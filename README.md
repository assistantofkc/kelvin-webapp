# 中文詞彙測試 (Chinese Vocabulary Test)

🌐 **Live Demo**: https://assistantofkc.pythonanywhere.com

## 簡介

呢個係一個中文詞彙測試工具，用戶輸入詞彙後，系統會自動生成填空題測驗。

### 功能特點

- ✅ 輸入中文詞彙，AI 自動生成填空題
- ✅ 批次式題目（每批 4 題）
- ✅ 支援多批次測驗
- ✅ 累積分數顯示
- ✅ 繁體中文句子生成
- ✅ 4 個選擇題（1 個正確 + 3 個干擾選項）
- ✅ 響應式設計（支持桌面和手機）

## 使用方法

1. 喺輸入框輸入中文詞彙（用空格或換行分隔）
2. 撳「開始測試」
3. 完成每批題目後可以繼續下一批
4. 完成所有批次後可以看到總分

## 技術架構

- **前端**: HTML5 + CSS3 + JavaScript (Vanilla)
- **後端**: Flask (Python)
- **AI API**: MiniMax-M2.7
- **托管**: PythonAnywhere

## 版本歷史

- v5.43 - 修復 blockerMsg 清理導致嘅 debugEl undefined 問題
- v5.41 - 修復最後一批 button 顯示問題
- v5.37 - blockerMsg 清理完成備份

## 文件結構

```
webapp/
├── app.py                  # Flask 後端
├── requirements.txt         # Python 依賴
├── templates/
│   ├── index.html         # 個人首頁
│   └── vocab_test.html     # 詞彙測試頁面
└── README.md
```

## 部署

詳細部署說明請睇 [DEPLOY.md](./DEPLOY.md)