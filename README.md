# arXiv Daily Feishu

arXiv Daily Feishu 是一个自动化工具，用于从 arXiv 获取每日更新的论文摘要，并通过飞书推送通知。

## 功能
- 每日从 arXiv 抓取最新论文数据。
- 支持通过飞书推送每日摘要。
- 可配置代理环境，适应不同网络环境。

## 安装

1. 克隆项目：
   ```bash
   git clone <repository-url>
   cd arxiv-daily-feishu
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用

在项目根目录下运行以下命令启动每日任务：
```bash
python -m src
```

## 配置

- 代理配置：
  项目支持代理环境，相关配置可在 `src/config/proxy.py` 中设置。

## 依赖

项目依赖的主要 Python 包包括：
- aiohttp
- feedparser
- python-dateutil
- httpx
- pydantic
- beautifulsoup4

完整依赖请参考 [requirements.txt](requirements.txt)。

## 贡献

欢迎提交 Issue 或 Pull Request 来改进本项目。

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](LICENSE)。