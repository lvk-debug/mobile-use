# mobile-use 测试用例文档

---

## M1 - 骨架：项目结构 + Device 连接 + 基础交互

### 测试文件清单

| 测试文件 | 测试类 | 用例数 |
|---------|--------|--------|
| `tests/test_connection.py` | TestConnectionConfig | 2 |
| `tests/test_connection.py` | TestConnectionManager | 3 |
| `tests/test_device.py` | TestDeviceInfo | 1 |
| `tests/test_device.py` | TestAppInfo | 1 |
| `tests/test_device.py` | TestDeviceBasicInfo | 3 |
| `tests/test_device.py` | TestDeviceInteraction | 5 |
| **合计** | | **15** |

---

### 1. ConnectionConfig 数据模型

#### TC-1.1 默认值验证
- **测试文件**: `tests/test_connection.py::TestConnectionConfig::test_default_values`
- **前置条件**: 仅提供 serial
- **测试步骤**:
  1. 创建 `ConnectionConfig(serial="emulator-5554")`
- **预期结果**:
  - `connect_type` 默认为 `"usb"`
  - `command_timeout` 默认为 `10.0`
  - `skip_waiting` 默认为 `False`
  - `server_url` 默认为 `None`

#### TC-1.2 自定义值验证
- **测试文件**: `tests/test_connection.py::TestConnectionConfig::test_custom_values`
- **前置条件**: 无
- **测试步骤**:
  1. 创建 `ConnectionConfig` 并指定所有字段
- **预期结果**:
  - 所有字段与传入值一致

---

### 2. ConnectionManager 连接管理

#### TC-2.1 连接成功返回 Device
- **测试文件**: `tests/test_connection.py::TestConnectionManager::test_connect_returns_device`
- **前置条件**: mock `u2.connect` 返回模拟设备
- **测试步骤**:
  1. 创建 `ConnectionManager`
  2. 调用 `connect(ConnectionConfig(serial="emulator-5554"))`
- **预期结果**:
  - 返回 `Device` 实例
  - `device.serial == "emulator-5554"`
  - `u2.connect` 被调用且参数正确

#### TC-2.2 重连成功
- **测试文件**: `tests/test_connection.py::TestConnectionManager::test_reconnect_success`
- **前置条件**: mock `u2.connect` 可多次调用成功
- **测试步骤**:
  1. 先连接设备
  2. 调用 `reconnect(device, max_retries=3)`
- **预期结果**:
  - 返回新 `Device` 实例
  - `u2.connect` 被调用 ≥ 2 次

#### TC-2.3 重连耗尽抛异常
- **测试文件**: `tests/test_connection.py::TestConnectionManager::test_reconnect_exhausted`
- **前置条件**: mock `u2.connect` 第一次成功，后续全部抛 `ConnectionError`
- **测试步骤**:
  1. 先连接设备
  2. 调用 `reconnect(device, max_retries=3)`
- **预期结果**:
  - 抛出 `ConnectionError`
  - 异常消息包含 `"Failed to reconnect"`

#### TC-2.4 列出设备
- **测试文件**: `tests/test_connection.py::TestConnectionManager::test_list_devices`
- **前置条件**: mock `u2.Adb.devices` 返回两台设备
- **测试步骤**:
  1. 调用 `list_devices()`
- **预期结果**:
  - 返回 `["emulator-5554", "192.168.1.100:5555"]`

---

### 3. DeviceInfo / AppInfo 模型

#### TC-3.1 DeviceInfo 字段
- **测试文件**: `tests/test_device.py::TestDeviceInfo::test_fields`
- **测试步骤**:
  1. 构造 `DeviceInfo` 并赋值所有字段
- **预期结果**: 所有字段正确

#### TC-3.2 AppInfo 字段
- **测试文件**: `tests/test_device.py::TestAppInfo::test_fields`
- **测试步骤**:
  1. 构造 `AppInfo` 并赋值所有字段
- **预期结果**: 所有字段正确

---

### 4. Device 设备信息接口

#### TC-4.1 info() 返回设备信息
- **测试文件**: `tests/test_device.py::TestDeviceBasicInfo::test_info`
- **前置条件**: mock_u2_device 返回预设 device_info 和 window_size
- **测试步骤**:
  1. 调用 `await device.info()`
- **预期结果**:
  - 返回 `DeviceInfo` 实例
  - brand="Google", model="Pixel 7", sdk_version=34, android_version="14"
  - screen_width=1080, screen_height=2400

#### TC-4.2 current_app() 返回前台应用
- **测试文件**: `tests/test_device.py::TestDeviceBasicInfo::test_current_app`
- **前置条件**: mock_u2_device 返回预设 app_current
- **测试步骤**:
  1. 调用 `await device.current_app()`
- **预期结果**:
  - 返回 `AppInfo` 实例
  - package="com.android.launcher3"

#### TC-4.3 window_size() 返回屏幕分辨率
- **测试文件**: `tests/test_device.py::TestDeviceBasicInfo::test_window_size`
- **测试步骤**:
  1. 调用 `await device.window_size()`
- **预期结果**:
  - 返回 `(1080, 2400)`

---

### 5. Device 交互接口

#### TC-5.1 tap() 调用底层 click
- **测试文件**: `tests/test_device.py::TestDeviceInteraction::test_tap`
- **测试步骤**:
  1. 调用 `await device.tap(100, 200)`
- **预期结果**:
  - `mock_u2_device.click(100, 200)` 被调用一次

#### TC-5.2 input_text() 调用底层 send_keys
- **测试文件**: `tests/test_device.py::TestDeviceInteraction::test_input_text`
- **测试步骤**:
  1. 调用 `await device.input_text("Hello World")`
- **预期结果**:
  - `mock_u2_device.send_keys("Hello World")` 被调用一次

#### TC-5.3 swipe() 调用底层 swipe_ext
- **测试文件**: `tests/test_device.py::TestDeviceInteraction::test_swipe`
- **测试步骤**:
  1. 调用 `await device.swipe("up", distance=0.8)`
- **预期结果**:
  - `mock_u2_device.swipe_ext("up", scale=0.8)` 被调用一次

#### TC-5.4 press_back() 调用底层 press
- **测试文件**: `tests/test_device.py::TestDeviceInteraction::test_press_back`
- **测试步骤**:
  1. 调用 `await device.press_back()`
- **预期结果**:
  - `mock_u2_device.press("back")` 被调用一次

#### TC-5.5 screenshot() 返回 PNG bytes
- **测试文件**: `tests/test_device.py::TestDeviceInteraction::test_screenshot`
- **前置条件**: mock_u2_device.screenshot 返回 100x100 红色 PIL Image
- **测试步骤**:
  1. 调用 `await device.screenshot()`
- **预期结果**:
  - 返回 `bytes` 类型
  - 前 4 字节为 PNG 魔数 `\x89PNG`
