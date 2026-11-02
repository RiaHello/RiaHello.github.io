# RIA 个人网站

Vue 3 + Vite 静态网站，包含首页（`#home`）、关于我（`#resume`）和联系我（`#contact`）。联系页使用本地肖像视频，浏览器横向45%～50%固定正视，移出该区间即开始向对应一侧转头；区域外按距离连续转头，两端反向移动即可逐渐回正；支持查看关于我、复制微信和邮箱、访问 GitHub。

## 本地运行

```sh
npm install
npm run dev -- --host 127.0.0.1 --port 5175
```

访问 [网站首页](http://127.0.0.1:5175/#home) 或 [联系我](http://127.0.0.1:5175/#contact)。如已有 5175 服务，请复用现有服务。

验证构建时必须指定单独目录：

```sh
npm run build -- --outDir /tmp/ria-contact-build
```

现有 Vite 默认输出目录是 `docs`，直接运行默认构建可能清空这里的设计文档和功能说明。以上命令不部署网站。

## 页面功能与实现说明

打开 [功能说明 HTML](docs/project-console.html)，或运行本地服务后访问 [浏览器中的功能说明](http://127.0.0.1:5175/docs/project-console.html)。这是独立工程说明，不在主站导航中出现。

按真实页面阅读功能，展开技术详情可查看输入输出、带条件的流程、连续朝向映射、帧标定、平滑转头与 seek 合并、逐字计时、复制失败、共享导航、参数及源码位置。页面仅运行自身的锚点导航和来源路径复制，不调用网站业务或付费服务。

刷新命令（不需要新增依赖）：

```sh
node scripts/build-project-console.mjs
```

- `docs/project-map.json` 保存人工说明、来源函数/行号与核对时 SHA-256；生成器只读它，不修改核对基线。
- `docs/project-console.html` 是生成结果，可离线打开；复制被浏览器拒绝时显示可手选路径。
- 源码指纹一致只表示人工说明对应的文件版本一致，不代表运行测试通过；参数标为源码默认值，不伪装成环境配置或实测值。
- 源码变化或缺失会把相关功能/算法标为“待复核”，退出码为 `2`。须定向重读代码、修订说明与位置，确认无误后再手动更新相应 SHA-256；不能只改哈希消除提示。
- JSON 解析、结构校验或读取失败会生成明确错误页并返回 `1`，避免旧说明继续显示已核对。正常生成返回 `0`。
- 隔离验证可使用 `node scripts/build-project-console.mjs --root /tmp/ria-doc-fixture`；夹具需包含 `docs/project-map.json` 和其中引用的源码文件。此选项不改变真实项目。

页面动画在浏览器内完成；AI 简历问答通过独立 FastAPI 后端调用 DeepSeek。

## 重建肖像交互素材

已生成的 `src/assets/contact-gaze.mp4` 可直接使用。需要重建时安装 ffmpeg 后运行：

```sh
bash scripts/prepare-contact-gaze.sh
```

脚本从保留的 `contact-portrait.mp4` 保留左至正面的连续动作（含自然眨眼），连接右转姿态并插值到60fps，以全I帧编码输出，另存同一正面帧为海报。用户下载目录中的原视频不改动。更换素材时须重新标定转头帧号和正面帧。

## 标题压力动效

联系页的Let's talk.按用户提供的React Bits TextPressure示例移植为Vue，支持逐字符宽度/字重/倾斜、空闲波浪及点击/轻触波纹。字体从src/assets/fonts/RobotoFlex-Latin.woff2本地加载；源码与字体的上游出处和许可保留在public/licenses/，随构建输出。减少动态效果偏好下保持静态标题。

## 关于我页面：AI 简历助手

“关于我”页面底部新增简历问答。聊天通过同源 `/api/v1/resume/chat` 调用独立Python服务，本地Vite代理到 `http://127.0.0.1:8000`。前端保持纯文本渲染与页面内存会话，支持停止生成和清空对话，不保存到localStorage。

后端安装、Redis、配置、真实公开简历、完整字段/错误码、curl和部署说明见 [backend/README.md](backend/README.md)。真实简历只能放在 `backend/data/public_resume.md`，必须由你从示例复制并填写；示例不会用于真实回答。API Key、模型名、HMAC密钥必须配置在后端，不能写入Vite变量。

静态站点托管本身不能运行Python/Redis；部署时需提供后端服务并反向代理 `/api/`。本地运行需要配置后端密钥与公开简历；静态发布不会自动部署 Python/Redis。离线测试不代表已验证模型事实准确性。

当前模型服务为 DeepSeek：在 `backend/.env` 填写 `DEEPSEEK_API_KEY`，`DEEPSEEK_MODEL` 示例为 `deepseek-flash`。后端通过官方 OpenAI Python SDK 调用 DeepSeek Responses 接口；不是 OpenAI 平台 Key。
