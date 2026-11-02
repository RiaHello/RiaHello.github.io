# 肖像联系页：局部实现方案

本轮为既有 Vue 3 + Vite 静态网站页面修改，不改变后端、数据模型或部署。用户明确委托按参考融入现有网站，常规实现选择据此执行。

## 组件与导航

新增 `src/components/ContactPortrait.vue`，封装肖像、逐字文案、联系方式、联系页专用移动导航与反馈；向 App 发送 go-home / go-resume。App 在联系页隐藏旧外壳导航、Logo、装饰和 WaterField 实例，其他页面保持原内容。原 WaterField 文件保留。使用 #contact / #resume / #home 与状态同步，支持直达、刷新和浏览器前进后退；保留已有切换动画，避免并发切换留下过期回调。实际导航使用的 PageTransition 在卸载时移除 resize 监听并释放画布及粒子引用。

## 媒体、交互与异常

视频和海报存入本地 `src/assets/`，不上传第三方。保留原始优化视频 `contact-portrait.mp4`，通过 `bash scripts/prepare-contact-gaze.sh` 生成用于交互的 `contact-gaze.mp4` 和正面海报；用户原文件不改动。原片先左后右，之前两段映射在正面处存在时间跳跃；当前保留反向的原24fps连续帧8～30（含原片自然眨眼）、右侧帧65～78，拼成左→正面→右单调序列，OBMC光流插值到60fps。输出1254×720、196帧、3.266667秒、约3MB、H.264全I帧、faststart且无音轨，减少随机定位的解码开销。素材帧位置与代码同步：左10/60秒、正面120/60秒、右190/60秒。左到正面保留原始连续动作，避免跳过中间姿态后插帧产生双鼻/双嘴；中间没有时间轴跳转；新海报来自同一正面帧。插值画面已实际查看，真实移动设备兼容性仍需硬件验证。

正视区严格为浏览器宽度45%～50%，不再延伸到人物眼睛；用户缩小无响应区域的最新要求覆盖此前眼睛延伸规则。leftEdge=width×0.45，rightEdge=width×0.5。区内目标0，保持正面120/60秒；左侧(clientX-leftEdge)/leftEdge映射[-1,0]，右侧(clientX-rightEdge)/(width-rightEdge)映射[0,1]，分母至少1px。两侧连续回转，视口边缘钳制。resize按新视口重算，触屏横拖使用同一规则。收敛后同目标直接返回，不重复RAF或seek；删除不再参与判定的眼睛锚点及cover坐标计算。

animateGaze用35ms时间常数的指数平滑，dt最多50ms，误差小于0.001时吸附目标。timeForGaze分别线性映射左→正面和正面→右，但在0处时间连续。setTime量化到60fps帧格并加0.0001秒定位偏移，限制0…duration-1/60；flushSeek只允许一个在途seek，新输入覆盖最新目标，seeked后立即处理最新目标，无额外seek RAF。目标差小于半帧不重复定位。元数据就绪后定位正面；只有定位完成才显示video，加载或失败时显示海报。卸载或媒体出错取消朝向RAF。不提供range控制条；减少动态效果时触屏显式控制直接定位、不缓动，鼠标不自动跟随。视频无autoplay，muted、playsinline、preload=auto。桌面pointermove、手机按下后横拖，保留纵向滚动；不劫持按钮操作。

复制 API 成功后才提示成功，缺失或拒绝权限时给出原文供手动复制。“聊聊项目”使用href="#resume"并调用navigate('resume')，与关于我入口共用站内导航；GitHub 新页打开并带 rel=noopener noreferrer。导航按钮语义化，移动菜单管理焦点并支持 Escape。可访问姓名与介绍不依赖逐字动态内容。

## 验证与文件边界

当前本地服务 `http://127.0.0.1:5175/`；Playwright CLI 可用，使用独立会话。验证 1440×900、390×844、320×568、横屏，视频拖动收敛、真实复制、失败反馈、减少动态效果、菜单、刷新与导航。

现有 `vite.config.js` 的 outDir=docs，包含本轮文档及旧参考，构建验证必须显式覆盖：`npm run build -- --outDir /tmp/ria-contact-build`，不得清空 docs。不改变部署、不提交或推送 Git。保留已有 App.vue、Home_Menu.vue、WaterField.vue 的非本轮改动。

## TextPressure标题动效

新增Vue组件TextPressure，移植用户提供示例的逐字符距离压力、空闲wave和点击ripple；ContactPortrait只替换标题内部，不改肖像控制。原h1语义/可访问名称保持，拆字视觉节点aria-hidden，保留Let's talk.大小写、空格、米白正文和绿句点。组件自身管理监听、RAF、IntersectionObserver/ResizeObserver；卸载清理、离屏/隐藏/移动菜单打开时暂停，减少动态效果时静态，不影响纵向触屏滚动。

字体为本地src/assets/fonts/RobotoFlex-Latin.woff2（250160字节），OFL位于public/licenses/RobotoFlex-OFL.txt，构建会一同带出许可证。Google Fonts CSS声明该资源支持wght100～1000、wdth25～151及slnt -10～0；使用slnt代替示例里该字体不支持的ital轴。不引入React或新增运行依赖。标题保持原字号尺度，按容器与最大压力字宽适配，避免窄屏截字及字形变化挤压下方内容。字体加载失败应静态/回退字体可读。

radius=.5、smoothing=.5、idle=wave、idleSpeed=1、clickRipple=true、alpha=false、无描边；字体压力轴与点击波纹按实际字体范围钳制。逐帧先批量读取再写样式，避免读写交错；可用时按可见性暂停闲置动画。具体实现参数及来源将在交付说明按最终代码核对。

最终标题动画范围为wght250～950、wdth80～135、slnt0～-10，保留可读下限；静态回退500/100/0。波浪周期3.2秒，点击波纹1.3秒、最多6个。最大字体量测使用当前动画上限950/135/-10加右侧留白，窄容器仅缩放X、维持原字号及高度。字体load成功才启用动态；监听卸载清理与Intersection/ResizeObserver断开由组件自身处理。

介绍显示串displayIntroduction仅将Indie Hacker的内部空格替换为U+00A0，供打字层和intro-spacer共同使用；原introduction及sr-only文本不变，字符数也不变，保留计时与可访问原文。

背景装饰字采用本地Allura-Latin.woff2（26464字节），OFL见public/licenses/Allura-OFL.txt。ContactPortrait scoped样式声明字体，回退Snell Roundhand / Apple Chancery / cursive；纯CSS字号、灰色透明度、模糊与旋转，不引入额外动画监听或运行依赖。

## REQ-RESUME-AI 七层方案增量

依据用户完整规格docs/references/resume-assistant-requirements.txt与Solution/Planner resume_contract返回。1目标：公开简历为唯一人物事实来源；2接口：POST /api/v1/resume/chat和live/ready，默认JSON，Accept SSE事件delta:{request_id,delta}、done:{request_id,answer}、error:统一错误对象；3数据：严格Pydantic、UTF8字节上限与Unicode码点长度、内存会话、Redis仅存HMAC计数；4模型：Async Responses instructions固定规则，简历结构化数据单独输入，禁止外部自选配置，无工具/自动重试；5算法：校验→简历→IP原子额度→4路并发→全站原子预占→一次模型→最终校验，30/35秒截止及断连释放；6异常：沿用用户稳定错误码，SSE启动前HTTP错误，启动后error清空临时文本；7目录：backend独立Python3.11虚拟环境、配置/服务/prompts/data/tests/锁文件，Vue ResumeAssistant挂载关于我底部，Vite代理本地8000。固定1实例1worker；真实简历/API配置由用户提供，未提供时不宣称真实上游验收。

### DeepSeek服务商适配（2026-11-01，用户明确选择，Confirmed）

Solution/Planner resume_contract确认最小变更。保留AsyncOpenAI的异步Responses调用，固定base_url=https://api.deepseek.com。后端只读取DEEPSEEK_API_KEY、DEEPSEEK_MODEL；示例模型deepseek-flash，reasoning.effort=none用于短答；store=false、1500输出上限、无工具/无重试及原JSON/SSE契约不变。DeepSeek忽略store参数且Responses是无状态接口，不能将该参数等同于完整数据保留保证。真实.env由root保留已填值进行字段迁移，不打印密钥；没有真实简历和账户调用时只声明离线适配。

官方依据：https://api-docs.deepseek.com/guides/responses_api/ （地址/SDK/流事件/store兼容），https://api-docs.deepseek.com/api/create-response （reasoning.effort），https://api-docs.deepseek.com/ （当前模型名）。

### 昵称与会话可视范围

用户确认“石耳”为陈科瑾的网名，已在固定提示词及公开简历中记录名称对应，工作经历依据用户本轮补充合并。保留用户之前的提示词编辑。界面完整历史留在内存，约三轮问答高度/小屏封顶的滚动容器仅改变呈现；向模型发送最近3轮/6000码点的限制不变。
