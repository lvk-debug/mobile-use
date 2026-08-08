# mobile-use 需求规格文档

> 复刻 browser-use 架构，做 Android 端自然语言自动化 Agent。
> 底层驱动：uiautomator2 | 语言：Python 3.10+ | 输出形态：SDK 包

---

## 1. 项目定位

browser-use 让 LLM 操控浏览器；**mobile-use 让 LLM 操控 Android 手机**。

| 维度 | browser-use | mobile-use |
|------|------------|------------|
| 底层驱动 | Playwright | uiautomator2 |
| 状态源 | DOM / Accessibility Tree | UI Hierarchy (XML) / Screenshot |
| 交互原语 | click, type, scroll, navigate | tap, input_text, swipe, back, home |
| 目标平台 | Web 浏览器 | Android 设备（真机 / 模拟器） |
| 输出形态 | Python 包 | Python SDK 包 + MCP Server |

---

## 2. 核心架构（对齐 browser-use）

```
┌─────────────────────────────────────────────────────┐
│                    User / MCP Client                 │
│              (自然语言任务 / MCP Tool 调用)            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │     Agent      │  ← 主编排器（观察→思考→行动 循环）
              │  (agent.py)    │
              └───────┬────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │  Model   │ │Controller│ │  Device   │
   │ (LLM)   │ │          │ │  Pool     │
   └──────────┘ └────┬─────┘ └────┬─────┘
                     │            │
                     ▼            ▼
              ┌──────────┐ ┌──────────┐
              │ Action   │ │ u2_driver│
              │ Registry │ │          │
              └──────────┘ └────┬─────┘
                                │
                                ▼
                         ┌────────────┐
                         │  Android   │
                         │  Device    │
                         └────────────┘
```

### 2.1 模块职责

| 模块 | 文件/包名 | browser-use 对应 | 职责 |
|------|----------|-----------------|------|
| **Agent** | `agent/` | `Agent` | 主循环：获取设备状态 → 构造 Prompt → 调用 LLM → 解析动作 → 执行 → 重复 |
| **Model** | `model/` | LLM wrapper | 封装各 LLM API（OpenAI / Anthropic / 本地模型），统一输出结构化动作 |
| **Controller** | `controller/` | `Controller` | 动作注册表 + 执行调度；接收 LLM 输出，查找并执行对应 handler |
| **Action** | `action/` | Pydantic action models | 定义每种可执行动作的参数 schema（tap, swipe, input_text, launch_app…） |
| **u2_driver** | `driver/` | BrowserContext | 封装 uiautomator2，提供统一设备操作接口（点击、滑动、截图、dump_hierarchy） |
| **Device Pool** | `device_pool/` | —（mobile-use 独有） | 多设备连接管理、分配、回收；支持 USB/WiFi 连接 |
| **MCP Server** | `mcp_server/` | —（mobile-use 独有） | 暴露 MCP 协议接口（stdio/SSE），将手机能力封装为 Tools & Resources |
| **State** | `state/` | BrowserState | 采集并结构化设备当前状态（UI 元素树 + 截图 + 元信息） |

---

## 3. 功能需求

### 3.1 Agent（核心编排器）

#### 3.1.1 主循环（Agent Loop）

```
while not done and step < max_steps:
    1. state = device.get_state()          # 采集设备状态
    2. prompt = build_prompt(task, state, history)  # 构造 LLM 输入
    3. response = llm.invoke(prompt)       # 调用 LLM
    4. action = parse_action(response)     # 解析结构化输出
    5. result = controller.execute(action) # 执行动作
    6. history.append(step)                # 记录历史
    7. if action.type == "done": break
```

#### 3.1.2 Agent 配置项

```python
class AgentConfig:
    task: str                    # 自然语言任务描述
    llm: BaseChatModel           # LLM 实例（LangChain 兼容）
    max_steps: int = 30          # 最大步数
    max_errors: int = 3          # 连续错误容忍次数
    use_vision: bool = True      # 是否使用截图（多模态）
    system_prompt: str = None    # 自定义 system prompt
    controller: Controller = None # 自定义 controller
    device: Device = None        # 指定设备（否则从 pool 分配）
```

#### 3.1.3 Agent 输出

```python
class AgentResult:
    task: str
    success: bool
    steps: list[AgentStep]       # 每一步的详细记录
    final_answer: str | None     # 最终结果/回答
    total_tokens: int            # token 消耗统计
    duration: float              # 总耗时
```

#### 3.1.4 AgentStep 记录

```python
class AgentStep:
    step_number: int
    state: DeviceState           # 执行前的设备状态
    action: ActionModel          # LLM 决定的动作
    result: ActionResult         # 执行结果
    llm_response: str            # LLM 原始输出
    timestamp: float
```

### 3.2 Model（LLM 封装）

- **兼容 LangChain**：接受 `langchain_core.language_models.BaseChatModel` 实例
- **结构化输出**：LLM 输出必须解析为 `AgentOutput` Pydantic 模型
- **多模态支持**：支持在 prompt 中附加截图（base64 / URL）
- **Token 统计**：记录每轮调用的 input/output tokens

```python
class AgentOutput(BaseModel):
    """LLM 的结构化输出"""
    thinking: str                # 推理过程（Chain of Thought）
    action: list[ActionModel]    # 要执行的动作列表（可批量）
```

### 3.3 Controller（动作调度）

#### 3.3.1 动作注册表

```python
controller = Controller()

@controller.action("点击屏幕上的元素")
async def tap(params: TapAction, device: Device) -> ActionResult:
    ...

@controller.action("在输入框中输入文字")
async def input_text(params: InputTextAction, device: Device) -> ActionResult:
    ...
```

#### 3.3.2 内置动作清单

| 动作名 | 参数 | 说明 |
|--------|------|------|
| `tap` | `x, y` 或 `element_index` | 点击坐标或元素 |
| `long_press` | `x, y, duration` | 长按 |
| `input_text` | `text`, `element_index?` | 输入文字到指定/当前焦点输入框 |
| `clear_text` | `element_index?` | 清空输入框 |
| `swipe` | `direction` 或 `sx, sy, ex, ey` | 滑动（上/下/左/右/自定义坐标） |
| `scroll` | `direction, distance?` | 滚动页面 |
| `press_key` | `key_name` | 按键（back / home / enter / recent） |
| `launch_app` | `package_name` | 启动应用 |
| `stop_app` | `package_name` | 停止应用 |
| `wait` | `seconds` 或 `element_condition` | 等待 |
| `screenshot` | — | 截图并返回（用于调试/确认） |
| `get_ui_hierarchy` | — | 获取当前 UI 树（调试用） |
| `done` | `answer` | 任务完成，返回结果 |
| `error` | `message` | 报告错误 |

#### 3.3.3 自定义动作扩展

```python
# 用户可注册自定义动作
@controller.action("打开微信并发送消息")
async def send_wechat_message(
    contact: str,
    message: str,
    device: Device
) -> ActionResult:
    # 自定义逻辑
    ...
```

### 3.4 u2_driver（设备驱动层）

#### 3.4.1 封装原则

- 将 uiautomator2 的原始 API 封装为更友好的异步接口
- 统一错误处理与重试逻辑
- 提供状态采集能力（UI 树解析 + 截图）

#### 3.4.2 Device 接口

```python
class Device:
    """单台设备的统一操作接口"""

    # === 连接信息 ===
    serial: str
    connect_type: str  # "usb" | "wifi"

    # === 设备信息 ===
    async def info(self) -> DeviceInfo          # 设备基本信息
    async def current_app(self) -> AppInfo      # 当前前台应用
    async def window_size(self) -> tuple[int, int]

    # === 基础交互 ===
    async def tap(self, x: int, y: int) -> None
    async def long_press(self, x: int, y: int, duration: float = 0.5) -> None
    async def double_tap(self, x: int, y: int) -> None
    async def swipe(self, direction: str, distance: float = 0.5) -> None
    async def swipe_coords(self, sx, sy, ex, ey, duration=0.5) -> None
    async def drag(self, sx, sy, ex, ey) -> None

    # === 文本输入 ===
    async def input_text(self, text: str) -> None
    async def clear_text(self) -> None

    # === 按键 ===
    async def press_key(self, key: str) -> None   # back/home/enter/recent
    async def press_back(self) -> None
    async def press_home(self) -> None

    # === 应用管理 ===
    async def app_start(self, package: str, activity: str = None) -> None
    async def app_stop(self, package: str) -> None
    async def app_install(self, apk_path: str) -> None
    async def app_uninstall(self, package: str) -> None
    async def app_list(self) -> list[str]

    # === 状态采集（Agent 的眼睛）===
    async def screenshot(self) -> bytes           # PNG bytes
    async def get_ui_hierarchy(self) -> UIHierarchy  # 解析后的 UI 树
    async def get_state(self) -> DeviceState       # 组合：UI树 + 截图 + 元信息

    # === 元素定位 ===
    async def find_element(self, **selector) -> Element | None
    async def find_elements(self, **selector) -> list[Element]
```

#### 3.4.3 Element 接口

```python
class Element:
    """UI 元素抽象"""
    index: int                  # 在 UI 树中的索引（供 LLM 引用）
    text: str
    resource_id: str
    class_name: str
    content_desc: str
    bounds: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    clickable: bool
    scrollable: bool
    enabled: bool

    async def click(self) -> None
    async def long_click(self) -> None
    async def set_text(self, text: str) -> None
    async def get_text(self) -> str
    async def scroll_to(self, direction: str) -> None
```

### 3.5 State（设备状态采集）

#### 3.5.1 DeviceState

```python
class DeviceState:
    """设备当前状态的结构化表示，作为 LLM 的输入上下文"""
    screenshot: bytes | None        # 截图（use_vision=True 时采集）
    ui_hierarchy: UIHierarchy       # 解析后的 UI 元素树
    current_app: AppInfo            # 前台应用信息
    device_info: DeviceInfo         # 设备基础信息
    timestamp: float
```

#### 3.5.2 UIHierarchy（UI 树解析）

```python
class UIHierarchy:
    """解析 dump_hierarchy() 的 XML 为结构化数据"""
    elements: list[UIElement]       # 扁平化元素列表（带 index）
    tree: dict                      # 原始树形结构（备用）

    def to_prompt_text(self) -> str:
        """转换为 LLM 可读的文本表示
        格式示例：
        [0] Button "确定" (clickable, bounds=[100,200,300,250])
        [1] EditText "请输入搜索内容" (clickable, bounds=[50,100,700,150])
        [2] TextView "搜索" (bounds=[720,100,800,150])
        """

    def to_simplified_text(self, max_elements: int = 100) -> str:
        """精简版，过滤不可交互元素，控制 token 消耗"""
```

### 3.6 Device Pool（设备池）

#### 3.6.1 多设备管理

```python
class DevicePool:
    """管理多台设备的连接与分配"""

    async def discover(self) -> list[str]              # 发现已连接设备
    async def connect(self, serial: str) -> Device     # 连接指定设备
    async def connect_all(self) -> list[Device]        # 连接所有设备
    async def get_device(self, serial: str = None) -> Device  # 获取设备（无则分配）
    async def release(self, device: Device) -> None    # 归还设备
    async def disconnect_all(self) -> None

    @property
    def available(self) -> list[Device]                # 可用设备列表
    @property
    def busy(self) -> list[Device]                     # 使用中设备列表
```

### 3.7 MCP Server（MCP 服务端）

#### 3.7.1 传输模式

| 模式 | 适用场景 | 启动方式 |
|------|---------|---------|
| **stdio** | 本地集成（Claude Desktop, CLI） | `mobile-use mcp --transport stdio` |
| **SSE** | 远程集成（Dify, LangGraph, Web） | `mobile-use mcp --transport sse --port 8765` |

#### 3.7.2 暴露的 MCP Tools

| Tool 名称 | 描述 | 参数 |
|-----------|------|------|
| `device_list` | 列出所有已连接设备 | — |
| `device_info` | 获取设备信息 | `serial` |
| `tap` | 点击屏幕坐标 | `serial, x, y` |
| `input_text` | 输入文字 | `serial, text` |
| `swipe` | 滑动 | `serial, direction` 或 `serial, sx, sy, ex, ey` |
| `press_key` | 按键 | `serial, key` |
| `screenshot` | 截图 | `serial` |
| `get_ui_hierarchy` | 获取 UI 元素树 | `serial, simplified?` |
| `launch_app` | 启动应用 | `serial, package_name` |
| `stop_app` | 停止应用 | `serial, package_name` |
| `run_task` | 执行自然语言任务（调用 Agent） | `serial, task, max_steps?` |

#### 3.7.3 暴露的 MCP Resources

| Resource URI | 描述 |
|-------------|------|
| `device://{serial}/screenshot` | 设备实时截图 |
| `device://{serial}/ui` | 设备 UI 层级 |
| `device://{serial}/info` | 设备信息 |

#### 3.7.4 MCP Server 使用示例

```python
# 方式 1：SDK 内嵌启动
from mobile_use.mcp_server import create_mcp_server
server = create_mcp_server(device_pool=pool)
await server.run(transport="sse", port=8765)

# 方式 2：CLI 启动
# mobile-use mcp --transport sse --port 8765
```

---

## 4. 两种使用模式

### 4.1 模式 A：SDK 直接调用

```python
from mobile_use import Agent, DevicePool
from langchain_openai import ChatOpenAI

# 连接设备
pool = DevicePool()
device = await pool.connect("emulator-5554")

# 创建 Agent 并执行任务
agent = Agent(
    task="打开设置，找到 WiFi 选项并截图",
    llm=ChatOpenAI(model="gpt-4o"),
    device=device,
    max_steps=20,
)
result = await agent.run()

print(result.success)         # True
print(result.final_answer)    # "已打开 WiFi 设置页面，截图已保存"
print(result.steps)           # 详细的执行步骤
```

### 4.2 模式 B：MCP 服务模式

```bash
# 启动 MCP Server（stdio 模式，供 Claude Desktop 等本地客户端）
mobile-use mcp --transport stdio

# 启动 MCP Server（SSE 模式，供 Dify/LangGraph 等远程客户端）
mobile-use mcp --transport sse --port 8765
```

外部 MCP Client 通过标准 MCP 协议调用上述 Tools / Resources，无需关心底层实现。

---

## 5. Prompt 工程

### 5.1 System Prompt 结构

```
你是 mobile-use Agent，一个通过自然语言操控 Android 手机的 AI 助手。

## 你的能力
你可以操控 Android 手机完成各种任务，包括但不限于：
- 打开/关闭应用
- 点击、滑动、输入文字
- 读取屏幕内容
- 截图确认操作结果

## 当前设备状态
{device_state}

## 可用的动作
{available_actions}

## 输出格式
请以 JSON 格式输出你的决策：
{
  "thinking": "你的推理过程",
  "action": [
    {"action_name": "tap", "params": {"x": 100, "y": 200}}
  ]
}

## 规则
1. 每一步只做一个或少量动作
2. 如果不确定元素位置，先截图或获取 UI 树
3. 如果任务无法完成，使用 done 动作并说明原因
4. 避免无效重复操作
```

### 5.2 多模态 Prompt

当 `use_vision=True` 时，每轮将截图作为图片附加到 prompt 中，LLM 可结合视觉信息判断元素位置。

---

## 6. 非功能需求

### 6.1 性能

| 指标 | 目标 |
|------|------|
| 单步执行延迟（不含 LLM） | < 2s |
| UI Hierarchy 解析 | < 500ms |
| 截图采集 | < 1s |
| MCP 请求响应 | < 100ms（不含 Agent 执行） |

### 6.2 可靠性

- u2_driver 连接断开时自动重连（最多 3 次）
- 动作执行失败时返回明确错误信息，由 LLM 决定重试/替代方案
- Agent 连续错误超过阈值时安全退出并返回已执行步骤

### 6.3 可扩展性

- Controller 支持运行时注册自定义动作（装饰器模式）
- Model 层可替换任意 LangChain 兼容 LLM
- MCP Server 支持自定义 Tool 注册

### 6.4 可观测性

- 每步记录 LLM 输入/输出、动作执行结果
- 支持 step callback（`on_step_start`, `on_step_end`）
- Token 消耗统计

### 6.5 日志

- 结构化日志（JSON 格式）
- 可配置日志级别（DEBUG / INFO / WARNING / ERROR）
- 敏感信息脱敏

---

## 7. 项目结构（建议）

```
mobile-use/
├── pyproject.toml
├── README.md
├── src/
│   └── mobile_use/
│       ├── __init__.py              # 导出 Agent, DevicePool 等公共 API
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── agent.py             # Agent 主类
│       │   ├── views.py             # AgentConfig, AgentResult, AgentStep
│       │   └── prompts.py           # System prompt 模板
│       ├── model/
│       │   ├── __init__.py
│       │   └── model.py             # LLM 封装，结构化输出解析
│       ├── controller/
│       │   ├── __init__.py
│       │   ├── controller.py        # Controller 类 + 动作注册表
│       │   └── registry.py          # @action 装饰器
│       ├── action/
│       │   ├── __init__.py
│       │   ├── base.py              # ActionModel 基类
│       │   ├── tap.py               # TapAction
│       │   ├── input_text.py        # InputTextAction
│       │   ├── swipe.py             # SwipeAction
│       │   ├── navigation.py        # PressKeyAction, BackAction, HomeAction
│       │   ├── app.py               # LaunchAppAction, StopAppAction
│       │   ├── done.py              # DoneAction
│       │   └── ...
│       ├── driver/
│       │   ├── __init__.py
│       │   ├── device.py            # Device 类（u2 封装）
│       │   ├── element.py           # Element 类
│       │   └── connection.py        # 连接管理、重连逻辑
│       ├── state/
│       │   ├── __init__.py
│       │   ├── state.py             # DeviceState
│       │   └── ui_hierarchy.py      # UIHierarchy 解析（XML → 结构化）
│       ├── device_pool/
│       │   ├── __init__.py
│       │   └── pool.py              # DevicePool 多设备管理
│       ├── mcp_server/
│       │   ├── __init__.py
│       │   ├── server.py            # MCP Server 创建与启动
│       │   ├── tools.py             # MCP Tools 定义
│       │   └── resources.py         # MCP Resources 定义
│       └── utils/
│           ├── __init__.py
│           ├── logger.py            # 日志工具
│           └── image.py             # 截图处理（压缩、base64）
├── tests/
│   ├── test_agent.py
│   ├── test_controller.py
│   ├── test_driver.py
│   ├── test_state.py
│   └── test_mcp_server.py
└── examples/
    ├── sdk_basic.py                 # SDK 基础用法
    ├── sdk_custom_action.py         # 自定义动作
    ├── mcp_stdio.py                 # MCP stdio 模式
    └── mcp_sse.py                   # MCP SSE 模式
```

---

## 8. 依赖清单

| 包 | 用途 |
|----|------|
| `uiautomator2` | Android 设备自动化驱动 |
| `langchain-core` | LLM 抽象层（BaseChatModel） |
| `pydantic` | 数据模型 & 结构化输出校验 |
| `mcp` (python-sdk) | MCP Server 实现 |
| `Pillow` | 截图图像处理 |
| `lxml` | UI Hierarchy XML 解析 |
| `loguru` | 结构化日志 |
| `httpx` | HTTP 客户端（SSE 传输） |

---

## 9. 里程碑

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| **M1 - 骨架** | 项目结构 + Device 连接 + 基础交互（tap/swipe/input） | 可连接设备并执行基础操作 |
| **M2 - 眼睛** | UI Hierarchy 解析 + 截图 + DeviceState | Agent 可感知设备状态 |
| **M3 - 大脑** | Agent Loop + Controller + 动作注册 + LLM 集成 | 端到端自然语言驱动 |
| **M4 - MCP** | MCP Server（stdio + SSE）+ Tools & Resources | 外部 MCP Client 可调用 |
| **M5 - 多设备** | Device Pool + 多设备并发 | 支持同时操控多台设备 |
| **M6 - 打磨** | 错误恢复 + 日志 + 回调 + 文档 + PyPI 发布 | 生产可用 |

---

## 10. 与 browser-use 的关键差异

| 差异点 | 说明 |
|--------|------|
| **无 URL 导航** | 手机没有地址栏，用 `launch_app` 替代 |
| **UI 树 ≠ DOM** | XML 层级结构不同，需要自定义解析器 |
| **坐标系** | 手机屏幕坐标，需要处理不同分辨率适配 |
| **多设备** | 手机场景天然多设备，需 Device Pool |
| **按键差异** | back / home / recent 等 Android 特有按键 |
| **应用生命周期** | install / uninstall / start / stop / clear |
| **MCP 输出** | 手机能力需要额外封装为 MCP 协议接口 |
