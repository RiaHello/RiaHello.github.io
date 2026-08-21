
export const profileData = {
  name: "陈科瑾 (石耳/RIA)",
  title: "AI应用开发工程师",
  tags: ["极客", "产品", "项目思维"],

  skills: {
    ai: ["PyTorch微调", "LoRA/QLORA", "RAG系统", "LangChain", "GraphRAG", "Agent开发"],
    backend: ["Python (FastAPI)", "Java (Spring Boot)", "DDD架构"],
    frontend: ["Vue 3", "TypeScript", "交互设计"],
    infra: ["Docker", "VLLM部署", "Kubernetes"]
  },

  projects: [
    {
      title: "智能法律咨询系统 (AI+法律)",
      period: "2025.04 - 2025.11",
      role: "核心开发",
      highlights: [
        "OCR+大模型：15万+判决书数据处理，OCR识别+结构化提取，构建'案例+法条'知识库，检索准确率90%+",
        "模型微调 (SFT)：基于Qwen/DeepSeek，LoRA (Rank=8)微调，优化Prompt工程，提升法律问答专业性",
        "Multi-Agent协作：设计'案例检索→法条匹配→答案生成→质量审核'四阶段Agent流程，实现复杂法律推理",
        "生产部署：Docker+VLLM推理服务，K8s管理，支持100+ QPS"
      ],
      tech: ["PyTorch", "LoRA", "LangChain", "VLLM", "Docker", "K8s"]
    },
    {
      title: "企业知识库智能问答 (RAG系统)",
      period: "2024.08 - 2024.11",
      role: "技术负责人",
      highlights: [
        "ETL数据处理：Excel多源数据清洗，Python自动化，Alpaca格式标准化",
        "RAG架构：混合检索(向量+关键词)，'问题改写'模块提升召回，Few-shot优化生成质量",
        "模型选型：对比Qwen-1.7B/8B，权衡推理速度与效果，最终Qwen-8B达96.5%准确率",
        "全栈实现：Spring Boot + Dify集成，快速MVP上线，迭代周期缩短30天"
      ],
      tech: ["RAG", "LangChain", "Dify", "FAISS", "Spring Boot"]
    },
    {
      title: "GraphRAG知识图谱增强检索",
      period: "2024研究项目",
      highlights: [
        "实现基于知识图谱的RAG系统，用LLM提取实体关系构建图谱",
        "NetworkX图分析，优化'社区发现'算法提升检索相关性",
        "Re-rank重排序机制，提升答案准确性"
      ],
      tech: ["GraphRAG", "NetworkX", "LLM", "知识图谱"]
    },
    {
      title: "医疗问答系统 (PromptCBLUE-v2)",
      period: "2024竞赛项目",
      highlights: [
        "Prompt工程优化，设计任务特定提示模板",
        "LoRA/Adapter高效微调，参数量减少90%",
        "医疗领域知识增强，提升专业问答质量"
      ],
      tech: ["Prompt Engineering", "LoRA", "医疗NLP"]
    }
  ],

  technicalDepth: {
    title: "Agent系统架构经验",
    items: [
      {
        topic: "Multi-Agent协作设计",
        description: "法律咨询系统中实现四阶段Agent流程：案例检索Agent→法条匹配Agent→答案生成Agent→质量审核Agent。每个Agent专注单一职责，通过状态传递协作"
      },
      {
        topic: "LangGraph状态管理",
        description: "理解LangGraph的图状态机制，设计节点间的状态流转，处理条件分支和循环逻辑，实现复杂推理链路"
      },
      {
        topic: "RAG系统优化",
        description: "从基础RAG到GraphRAG演进，对比向量检索、关键词检索、图谱检索的适用场景，实践Re-rank、问题改写等优化技术"
      },
      {
        topic: "模型微调工程化",
        description: "LoRA/QLORA参数高效微调实践，对比不同Rank值的效果与成本，掌握从数据准备到部署的完整流程"
      }
    ]
  },

  achievements: [
    "2024美国大学生数学建模竞赛 (MCM/ICM) Meritorious Winner (一等奖)",
    "PromptCBLUE-v2医疗问答竞赛 Top 20"
  ],

  education: {
    school: "南京理工大学",
    major: "计算机科学与技术",
    period: "2021.9 - 2025.7",
    gpa: "专业前20%"
  }
};
