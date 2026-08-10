"""M3 动作模型单元测试"""

from __future__ import annotations

import pytest

from mobile_use.action import (
    ActionModel,
    ActionResult,
    BackAction,
    ClearTextAction,
    DoneAction,
    ErrorAction,
    HomeAction,
    InputTextAction,
    LaunchAppAction,
    LongPressAction,
    PressKeyAction,
    ScrollAction,
    StopAppAction,
    SwipeAction,
    TapAction,
    WaitAction,
)


class TestActionModel:
    """ActionModel 基类测试"""

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            TapAction(x=1, y=2, unknown_field="bad")


class TestTapAction:
    def test_by_coords(self):
        a = TapAction(x=100, y=200)
        assert a.x == 100
        assert a.y == 200
        assert a.element_index is None

    def test_by_element_index(self):
        a = TapAction(element_index=5)
        assert a.element_index == 5
        assert a.x is None

    def test_default_none(self):
        a = TapAction()
        assert a.x is None
        assert a.y is None
        assert a.element_index is None


class TestLongPressAction:
    def test_defaults(self):
        a = LongPressAction(x=10, y=20)
        assert a.duration == 0.5

    def test_custom_duration(self):
        a = LongPressAction(x=10, y=20, duration=2.0)
        assert a.duration == 2.0


class TestInputTextAction:
    def test_basic(self):
        a = InputTextAction(text="hello")
        assert a.text == "hello"
        assert a.element_index is None

    def test_with_element(self):
        a = InputTextAction(text="world", element_index=3)
        assert a.element_index == 3


class TestClearTextAction:
    def test_default(self):
        a = ClearTextAction()
        assert a.element_index is None


class TestSwipeAction:
    def test_by_direction(self):
        a = SwipeAction(direction="up", distance=0.8)
        assert a.direction == "up"
        assert a.distance == 0.8

    def test_by_coords(self):
        a = SwipeAction(sx=100, sy=200, ex=300, ey=400)
        assert a.sx == 100

    def test_default_distance(self):
        a = SwipeAction(direction="down")
        assert a.distance == 1.0


class TestScrollAction:
    def test_basic(self):
        a = ScrollAction(direction="down")
        assert a.direction == "down"
        assert a.distance == 2.0


class TestNavigationActions:
    def test_press_key(self):
        a = PressKeyAction(key_name="back")
        assert a.key_name == "back"

    def test_back(self):
        a = BackAction()
        assert isinstance(a, ActionModel)

    def test_home(self):
        a = HomeAction()
        assert isinstance(a, ActionModel)


class TestAppActions:
    def test_launch(self):
        a = LaunchAppAction(package_name="com.android.settings")
        assert a.package_name == "com.android.settings"
        assert a.activity is None

    def test_launch_with_activity(self):
        a = LaunchAppAction(package_name="com.test", activity=".Main")
        assert a.activity == ".Main"

    def test_stop(self):
        a = StopAppAction(package_name="com.test")
        assert a.package_name == "com.test"


class TestWaitAction:
    def test_default(self):
        a = WaitAction()
        assert a.seconds == 1.0

    def test_custom(self):
        a = WaitAction(seconds=3.5)
        assert a.seconds == 3.5


class TestDoneAction:
    def test_default(self):
        a = DoneAction()
        assert a.answer == ""

    def test_with_answer(self):
        a = DoneAction(answer="任务已完成")
        assert a.answer == "任务已完成"


class TestErrorAction:
    def test_default(self):
        a = ErrorAction()
        assert a.message == ""

    def test_with_message(self):
        a = ErrorAction(message="找不到元素")
        assert a.message == "找不到元素"


class TestActionResult:
    def test_success(self):
        r = ActionResult(success=True, message="ok")
        assert r.success is True
        assert r.data is None

    def test_failure(self):
        r = ActionResult(success=False, message="failed")
        assert r.success is False

    def test_with_data(self):
        r = ActionResult(data={"key": "value"})
        assert r.data == {"key": "value"}
