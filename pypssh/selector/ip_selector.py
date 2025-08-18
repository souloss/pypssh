import ipaddress
import re
from typing import List, Set, Union, Iterator
from dataclasses import dataclass


@dataclass
class IPRange:
    start: ipaddress.IPv4Address
    end: ipaddress.IPv4Address

    def contains(self, ip: ipaddress.IPv4Address) -> bool:
        return self.start <= ip <= self.end

    def __iter__(self) -> Iterator[ipaddress.IPv4Address]:
        current = int(self.start)
        end = int(self.end)
        while current <= end:
            yield ipaddress.IPv4Address(current)
            current += 1


class IPSelector:
    """IP选择表达式解析器

    支持的表达式格式：
    - 单IP: 192.168.1.1
    - CIDR: 192.168.1.0/24
    - 范围: 192.168.1.1-192.168.1.100
    - 列表: 192.168.1.1,192.168.1.5,192.168.1.10
    - 排除: 192.168.1.0/24 !192.168.1.100,192.168.1.101
    - 字段范围: 192.[22:26,33].[95:99].[95:99]
    - 混合: 192.168.1.0/24,10.0.0.1-10.0.0.50
    """

    def __init__(self, expression: str):
        self.expression = expression.strip()
        self._include_ranges: List[
            Union[
                ipaddress.IPv4Network, IPRange, ipaddress.IPv4Address, FieldRangeIPRange
            ]
        ] = []
        self._exclude_ranges: List[
            Union[
                ipaddress.IPv4Network, IPRange, ipaddress.IPv4Address, FieldRangeIPRange
            ]
        ] = []
        self._parse()

    def _parse(self):
        """解析IP表达式"""
        # 分离包含和排除部分
        if "!" in self.expression:
            include_part, exclude_part = self.expression.split("!", 1)
            self._parse_ranges(include_part.strip(), self._include_ranges)
            self._parse_ranges(exclude_part.strip(), self._exclude_ranges)
        else:
            self._parse_ranges(self.expression, self._include_ranges)

    def _parse_ranges(self, expression: str, target_list: List):
        """解析IP范围表达式"""
        parts = []
        current_part = []
        bracket_level = 0

        for char in expression:
            if char == "[":
                bracket_level += 1
                current_part.append(char)
            elif char == "]":
                bracket_level -= 1
                current_part.append(char)
            elif char == "," and bracket_level == 0:
                # 只有在不在方括号内时才分割
                parts.append("".join(current_part).strip())
                current_part = []
            else:
                current_part.append(char)

        # 添加最后一个部分
        if current_part:
            parts.append("".join(current_part).strip())

        for part in parts:
            if not part:
                continue
            # 检查是否包含字段范围表达式（如192.[22:26].[95:99].[95:99]）
            if "[" in part and "]" in part:
                # 解析字段范围表达式
                self._parse_field_range(part, target_list)
                continue
            if "-" in part and "/" not in part:
                # IP范围: 192.168.1.1-192.168.1.100
                start_str, end_str = part.split("-", 1)
                start_ip = ipaddress.IPv4Address(start_str.strip())
                end_ip = ipaddress.IPv4Address(end_str.strip())
                target_list.append(IPRange(start_ip, end_ip))
            elif "/" in part:
                # CIDR: 192.168.1.0/24
                target_list.append(ipaddress.IPv4Network(part, strict=False))
            else:
                # 单IP: 192.168.1.1
                target_list.append(ipaddress.IPv4Address(part))

    def _parse_field_range(self, expression: str, target_list: List):
        """解析字段范围表达式（如192.[22:26,33].[95:99].[95:99]）"""
        # 分割IP的四个字段
        fields = expression.split(".")
        if len(fields) != 4:
            raise ValueError(f"Invalid IP range expression: {expression}")

        # 解析每个字段的值
        field_values = []
        for field in fields:
            if "[" in field and "]" in field:
                # 处理范围表达式 [start:end] 或 [start,end] 或 [start:end,value]
                range_str = field[field.index("[") + 1 : field.index("]")]
                values = []

                # 分割多个范围或值
                for part in range_str.split(","):
                    if ":" in part:
                        # 处理 [start:end] 格式
                        start, end = map(int, part.split(":", 1))
                        values.extend(range(start, end + 1))
                    else:
                        # 处理单个值
                        values.append(int(part))

                # 去重并排序
                values = sorted(set(values))

                # 验证值范围
                if any(v < 0 or v > 255 for v in values):
                    raise ValueError(f"Invalid IP field value in {field}")

                field_values.append(values)
            else:
                # 处理普通数字字段
                try:
                    value = int(field)
                    if value < 0 or value > 255:
                        raise ValueError(f"Invalid IP field value: {value}")
                    field_values.append([value])
                except ValueError:
                    raise ValueError(f"Invalid IP field: {field}")

        # 计算总IP数量
        total_count = 1
        for values in field_values:
            total_count *= len(values)

        # 如果总IP数量过大，创建FieldRangeIPRange对象而不是生成所有IP
        if total_count > 10000:  # 设置阈值，超过此值使用延迟加载
            target_list.append(FieldRangeIPRange(field_values))
        else:
            # 对于小范围，仍然直接生成所有IP
            for a in field_values[0]:
                for b in field_values[1]:
                    for c in field_values[2]:
                        for d in field_values[3]:
                            ip_str = f"{a}.{b}.{c}.{d}"
                            try:
                                target_list.append(ipaddress.IPv4Address(ip_str))
                            except ipaddress.AddressValueError:
                                continue

    def matches(self, ip_str: str) -> bool:
        """检查IP是否匹配表达式"""
        try:
            ip = ipaddress.IPv4Address(ip_str)
        except ipaddress.AddressValueError:
            return False

        # 检查是否在包含范围内
        included = False
        for range_obj in self._include_ranges:
            if isinstance(range_obj, ipaddress.IPv4Network):
                if ip in range_obj:
                    included = True
                    break
            elif isinstance(range_obj, IPRange):
                if range_obj.contains(ip):
                    included = True
                    break
            elif isinstance(range_obj, ipaddress.IPv4Address):
                if ip == range_obj:
                    included = True
                    break
            elif isinstance(range_obj, FieldRangeIPRange):
                if range_obj.contains(ip):
                    included = True
                    break

        if not included:
            return False

        # 检查是否在排除范围内
        for range_obj in self._exclude_ranges:
            if isinstance(range_obj, ipaddress.IPv4Network):
                if ip in range_obj:
                    return False
            elif isinstance(range_obj, IPRange):
                if range_obj.contains(ip):
                    return False
            elif isinstance(range_obj, ipaddress.IPv4Address):
                if ip == range_obj:
                    return False
            elif isinstance(range_obj, FieldRangeIPRange):
                if range_obj.contains(ip):
                    return False

        return True

    def expand(self, limit: int = 10000) -> List[str]:
        """展开表达式为IP列表（内存优化版）"""
        if limit < 0:
            limit = 10000  # 负数limit使用默认值

        # 如果limit为0，直接返回空列表
        if limit == 0:
            return []

        # 使用有限大小的LRU缓存来去重
        from collections import OrderedDict

        seen_ips = OrderedDict()
        cache_size = min(limit * 2, 10000)  # 缓存大小为limit的2倍，最大10000

        result_ips = []

        # 生成器函数，按需生成IP
        def ip_generator():
            for range_obj in self._include_ranges:
                if isinstance(range_obj, ipaddress.IPv4Network):
                    yield from range_obj.hosts()
                elif isinstance(range_obj, IPRange):
                    yield from range_obj
                elif isinstance(range_obj, ipaddress.IPv4Address):
                    yield range_obj
                elif isinstance(range_obj, FieldRangeIPRange):
                    yield from range_obj.limited_iter(limit * 2)

        # 流式处理
        for ip in ip_generator():
            ip_str = str(ip)

            # 使用LRU缓存去重
            if ip_str in seen_ips:
                continue
            seen_ips[ip_str] = True
            # 如果缓存超过大小，移除最旧的项
            if len(seen_ips) > cache_size:
                seen_ips.popitem(last=False)

            # 检查排除规则
            excluded = False
            for range_obj in self._exclude_ranges:
                if isinstance(range_obj, ipaddress.IPv4Network):
                    if ip in range_obj:
                        excluded = True
                        break
                elif isinstance(range_obj, IPRange):
                    if range_obj.contains(ip):
                        excluded = True
                        break
                elif isinstance(range_obj, ipaddress.IPv4Address):
                    if ip == range_obj:
                        excluded = True
                        break
                elif isinstance(range_obj, FieldRangeIPRange):
                    if range_obj.contains(ip):
                        excluded = True
                        break

            if not excluded:
                result_ips.append(ip_str)
                if len(result_ips) >= limit:
                    break

        # 排序并返回
        return sorted(result_ips, key=lambda x: ipaddress.IPv4Address(x))


@dataclass
class FieldRangeIPRange:
    """表示由字段范围表达式生成的IP范围"""

    field_values: List[List[int]]  # 四个字段的值列表
    _total_count: int = None  # 缓存总IP数量

    def __post_init__(self):
        """计算总IP数量"""
        self._total_count = 1
        for values in self.field_values:
            self._total_count *= len(values)

    @property
    def total_count(self) -> int:
        """获取总IP数量"""
        return self._total_count

    def contains(self, ip: ipaddress.IPv4Address) -> bool:
        """检查IP是否在范围内（高效实现）"""
        # 将IP转换为四个整数字段
        ip_int = int(ip)
        fields = [
            (ip_int >> 24) & 0xFF,
            (ip_int >> 16) & 0xFF,
            (ip_int >> 8) & 0xFF,
            ip_int & 0xFF,
        ]

        # 检查每个字段是否在对应的值列表中
        for i, field_val in enumerate(fields):
            if field_val not in self.field_values[i]:
                return False
        return True

    def __iter__(self) -> Iterator[ipaddress.IPv4Address]:
        """迭代器，按需生成IP地址"""
        # 使用生成器避免一次性生成所有IP
        for a in self.field_values[0]:
            for b in self.field_values[1]:
                for c in self.field_values[2]:
                    for d in self.field_values[3]:
                        # 将四个字段组合成IP地址
                        ip_int = (a << 24) | (b << 16) | (c << 8) | d
                        yield ipaddress.IPv4Address(ip_int)

    def limited_iter(self, limit: int) -> Iterator[ipaddress.IPv4Address]:
        """限制数量的迭代器"""
        count = 0
        for a in self.field_values[0]:
            for b in self.field_values[1]:
                for c in self.field_values[2]:
                    for d in self.field_values[3]:
                        if count >= limit:
                            return
                        ip_int = (a << 24) | (b << 16) | (c << 8) | d
                        yield ipaddress.IPv4Address(ip_int)
                        count += 1
