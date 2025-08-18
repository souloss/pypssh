import re
import ipaddress
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from pypssh.core.models import *


class LabelSelector:
    """标签选择器：解析并匹配表达式"""

    def __init__(self, expression: str):
        self.raw_expression = expression.strip()
        self.conditions = self._split_conditions(self.raw_expression)

    def matches(self, labels: Dict[str, str]) -> bool:
        """检查标签是否匹配选择器"""
        if not self.conditions:
            return True  # 空表达式匹配所有
        return all(self._eval_condition(cond, labels) for cond in self.conditions)

    # -------------------------
    # 核心条件评估
    # -------------------------
    def _eval_condition(self, expr: str, labels: Dict[str, str]) -> bool:
        expr = expr.strip()
        if not expr:
            return True

        # 布尔否定
        if expr.startswith("!"):
            inner = expr[1:].strip()
            return not self._eval_condition(inner, labels)

        # 括号表达式
        if expr.startswith("(") and expr.endswith(")"):
            inner = expr[1:-1].strip()
            return self._eval_condition(inner, labels)

        # 特殊函数处理
        for func in [
            self._eval_has,
            self._eval_count,
            self._eval_string_func,
            self._eval_set_op,
            self._eval_numeric_comp,
            self._eval_equality,
        ]:
            res = func(expr, labels)
            if res is not None:
                return res

        # 默认不匹配
        return False

    # -------------------------
    # 条件类型评估方法
    # -------------------------
    def _eval_has(self, expr: str, labels: Dict[str, str]) -> Optional[bool]:
        """处理 has(key) / !has(key)"""
        if expr.startswith("has(") and expr.endswith(")"):
            key = expr[4:-1].strip()
            return key in labels
        if expr.startswith("!has(") and expr.endswith(")"):
            key = expr[5:-1].strip()
            return key not in labels
        return None

    def _eval_count(self, expr: str,labels: Dict[str, str]) -> Optional[bool]:
        """处理 count(key) 比较"""
        m = re.match(r"count\((\w+)\)\s*(==|!=|>=|<=|>|<)\s*(\d+)", expr)
        if m:
            key, op, num = m.groups()
            actual = self._get_count(labels, key)
            return self._compare(actual, op, int(num))
        return None

    def _eval_string_func(self, expr: str, labels: Dict[str, str]) -> Optional[bool]:
        """处理 startswith/endswith/contains/regex/len"""
        m = re.match(r"(\w+)\(([^,]+)(?:,\s*\"?([^\"]+)\"?)?\)", expr)
        if not m:
            return None
        func, key, arg = m.groups()
        key = key.strip()
        val = labels.get(key)
        if val is None:
            return False

        if func == "startswith":
            return arg is not None and val.startswith(arg)
        if func == "endswith":
            return arg is not None and val.endswith(arg)
        if func == "contains":
            return arg is not None and arg in val
        if func == "regex":
            try:
                return arg is not None and re.match(arg, val) is not None
            except re.error:
                return False
        if func == "len":
            m2 = re.match(r"len\(([^)]+)\)\s*([<>]=?|<=?)\s*(\d+)", expr)
            if not m2:
                return False
            key2, op, num = m2.groups()
            v = labels.get(key2.strip())
            if v is None:
                return False
            return self._compare_numbers(len(v), int(num), op)
        return None

    def _eval_set_op(self, expr: str, labels: Dict[str, str]) -> Optional[bool]:
        """处理 in / notin"""
        m = re.match(r"([\w\-\.]+)\s+(in|notin)\s*\(([^)]+)\)", expr)
        if not m:
            return None
        key, op, values = m.groups()
        vals = [v.strip().strip('"').strip("'") for v in values.split(",") if v.strip()]
        if not vals:
            return False
        actual = labels.get(key)
        return (actual in vals) if op == "in" else (actual not in vals)

    def _eval_equality(self, expr: str, labels: Dict[str, str]) -> Optional[bool]:
        """处理 = / !="""
        if "!=" in expr:
            key, val = expr.split("!=", 1)
            return labels.get(key.strip()) != val.strip().strip('"')
        if "=" in expr and "==" not in expr:
            key, val = expr.split("=", 1)
            return labels.get(key.strip()) == val.strip().strip('"')
        return None

    def _eval_numeric_comp(self, expr: str, labels: Dict[str, str]) -> Optional[bool]:
        """处理 key > num / key < num"""
        m = re.match(r"(\w+)\s*([<>]=?|<=?)\s*(\d+)", expr)
        if not m:
            return None
        key, op, num = m.groups()
        num_val = self._to_number(labels.get(key.strip()))
        if num_val is None:
            return False
        return self._compare_numbers(num_val, int(num), op)

    # -------------------------
    # 工具方法
    # -------------------------
    def _to_number(self, v: Optional[str]) -> Optional[int]:
        try:
            return int(v)
        except Exception:
            return None

    def _compare_numbers(self, left: int, right: int, op: str) -> bool:
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        return False

    def _compare(
        self, left: Union[int, float], op: str, right: Union[int, float]
    ) -> bool:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        raise ValueError(f"Unsupported operator: {op}")

    def _get_count(self, labels: Dict[str, str], label: str) -> int:
        value = labels.get(label)
        if value is None:
            return 0
        if isinstance(value, str) and value.isdigit():
            return int(value)
        if isinstance(value, (list, dict, set, tuple)):
            return len(value)
        return len(str(value))

    def _split_conditions(self, expr: str) -> List[str]:
        """仅在顶层拆分逗号，不拆分括号或引号内的逗号"""
        parts, buf, depth, in_quote = [], [], 0, None
        for c in expr:
            if c in ('"', "'"):
                if in_quote is None:
                    in_quote = c
                elif in_quote == c:
                    in_quote = None
                buf.append(c)
            elif c == "(" and in_quote is None:
                depth += 1
                buf.append(c)
            elif c == ")" and in_quote is None:
                depth -= 1
                buf.append(c)
            elif c == "," and depth == 0 and in_quote is None:
                part = "".join(buf).strip()
                if part:
                    parts.append(part)
                buf = []
            else:
                buf.append(c)
        if buf:
            parts.append("".join(buf).strip())
        return parts


# -------------------------
# IP 扩展工具
# -------------------------
def _expand_ip_expr(ip_expr: str) -> List[str]:
    ip_expr = ip_expr.strip()

    # 192.168.1.1-192.168.1.10
    if "-" in ip_expr:
        start, end = ip_expr.split("-", 1)
        start_ip = ipaddress.ip_address(start.strip())
        end_ip = ipaddress.ip_address(end.strip())
        if start_ip > end_ip:
            start_ip, end_ip = end_ip, start_ip
        ips, cur = [], start_ip
        while cur <= end_ip:
            ips.append(str(cur))
            cur += 1
        return ips

    # 192.168.1.[1:20]
    m = re.match(r"(\d+\.\d+\.\d+)\.\[(\d+):(\d+)\]", ip_expr)
    if m:
        prefix, s, e = m.groups()
        return [f"{prefix}.{i}" for i in range(int(s), int(e) + 1)]

    # 单 IP
    try:
        ipaddress.ip_address(ip_expr)
        return [ip_expr]
    except Exception:
        raise ValueError(f"Invalid IP expression: {ip_expr}")


def select_servers(
    hosts: List[Host], ip_expr: str = "", label_expr: str = ""
) -> List[Host]:
    """根据 IP 和标签表达式过滤服务器"""
    filtered = hosts
    if ip_expr is not None and ip_expr.strip():
        ips = _expand_ip_expr(ip_expr)
        filtered = [s for s in filtered if s.host in ips]

    if label_expr is not None and label_expr.strip():
        selector = LabelSelector(label_expr)
        filtered = [host for host in filtered if selector.matches(host.labels)]

    return filtered
