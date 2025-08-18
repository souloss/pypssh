import pytest
import ipaddress
from typing import List, Set, Union, Iterator
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

from pypssh.selector.ip_selector import IPRange, IPSelector


class TestIPRange:
    """测试IPRange类"""

    def test_contains(self):
        """测试IP范围包含检查"""
        start = ipaddress.IPv4Address("192.168.1.1")
        end = ipaddress.IPv4Address("192.168.1.10")
        ip_range = IPRange(start, end)

        # 测试范围内的IP
        assert ip_range.contains(ipaddress.IPv4Address("192.168.1.1"))
        assert ip_range.contains(ipaddress.IPv4Address("192.168.1.5"))
        assert ip_range.contains(ipaddress.IPv4Address("192.168.1.10"))

        # 测试范围外的IP
        assert not ip_range.contains(ipaddress.IPv4Address("192.168.1.0"))
        assert not ip_range.contains(ipaddress.IPv4Address("192.168.1.11"))

    def test_iter(self):
        """测试IP范围迭代"""
        start = ipaddress.IPv4Address("192.168.1.1")
        end = ipaddress.IPv4Address("192.168.1.3")
        ip_range = IPRange(start, end)

        ips = list(ip_range)
        expected = [
            ipaddress.IPv4Address("192.168.1.1"),
            ipaddress.IPv4Address("192.168.1.2"),
            ipaddress.IPv4Address("192.168.1.3"),
        ]

        assert ips == expected


class TestIPSelector:
    """测试IPSelector类"""

    def test_single_ip(self):
        """测试单IP表达式"""
        selector = IPSelector("192.168.1.1")

        assert selector.matches("192.168.1.1")
        assert not selector.matches("192.168.1.2")

        ips = selector.expand()
        assert ips == ["192.168.1.1"]

    def test_cidr(self):
        """测试CIDR表达式"""
        selector = IPSelector("192.168.1.0/24")

        # 测试范围内的IP
        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.1.100")
        assert selector.matches("192.168.1.254")

        # 测试范围外的IP
        assert not selector.matches("192.168.0.1")
        assert not selector.matches("192.168.2.1")

        # 测试展开
        ips = selector.expand(limit=5)
        assert len(ips) == 5
        assert ips[0] == "192.168.1.1"
        assert ips[1] == "192.168.1.2"

    def test_ip_range(self):
        """测试IP范围表达式"""
        selector = IPSelector("192.168.1.1-192.168.1.5")

        # 测试范围内的IP
        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.1.3")
        assert selector.matches("192.168.1.5")

        # 测试范围外的IP
        assert not selector.matches("192.168.1.0")
        assert not selector.matches("192.168.1.6")

        # 测试展开
        ips = selector.expand()
        expected = [
            "192.168.1.1",
            "192.168.1.2",
            "192.168.1.3",
            "192.168.1.4",
            "192.168.1.5",
        ]
        assert ips == expected

    def test_ip_list(self):
        """测试IP列表表达式"""
        selector = IPSelector("192.168.1.1,192.168.1.5,192.168.1.10")

        # 测试列表中的IP
        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.1.5")
        assert selector.matches("192.168.1.10")

        # 测试不在列表中的IP
        assert not selector.matches("192.168.1.2")
        assert not selector.matches("192.168.1.6")

        # 测试展开
        ips = selector.expand()
        expected = ["192.168.1.1", "192.168.1.5", "192.168.1.10"]
        assert ips == expected

    def test_exclude(self):
        """测试排除表达式"""
        selector = IPSelector("192.168.1.0/24 !192.168.1.100,192.168.1.101")

        # 测试包含的IP
        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.1.99")
        assert selector.matches("192.168.1.102")

        # 测试排除的IP
        assert not selector.matches("192.168.1.100")
        assert not selector.matches("192.168.1.101")

        # 测试展开
        ips = selector.expand(limit=103)
        assert "192.168.1.100" not in ips
        assert "192.168.1.101" not in ips
        assert "192.168.1.99" in ips
        assert "192.168.1.102" in ips

    def test_field_range_colon(self):
        """测试字段范围表达式（冒号分隔）"""
        selector = IPSelector("192.[22:24].[1:3].1")

        # 测试包含的IP
        assert selector.matches("192.22.1.1")
        assert selector.matches("192.22.2.1")
        assert selector.matches("192.22.3.1")
        assert selector.matches("192.23.1.1")
        assert selector.matches("192.24.3.1")

        # 测试不包含的IP
        assert not selector.matches("192.21.1.1")
        assert not selector.matches("192.25.1.1")
        assert not selector.matches("192.22.4.1")

        # 测试展开
        ips = selector.expand()
        assert len(ips) == 9  # 3 * 3 = 9
        assert "192.22.1.1" in ips
        assert "192.24.3.1" in ips

    def test_field_range_comma(self):
        """测试字段范围表达式（逗号分隔）"""
        selector = IPSelector("192.[22,24].[1,3].1")

        # 测试包含的IP
        assert selector.matches("192.22.1.1")
        assert selector.matches("192.22.3.1")
        assert selector.matches("192.24.1.1")
        assert selector.matches("192.24.3.1")

        # 测试不包含的IP
        assert not selector.matches("192.23.1.1")
        assert not selector.matches("192.22.2.1")

        # 测试展开
        ips = selector.expand()
        assert len(ips) == 4  # 2 * 2 = 4
        assert "192.22.1.1" in ips
        assert "192.24.3.1" in ips

    def test_field_range_single_value(self):
        """测试字段范围表达式（单个值）"""
        selector = IPSelector("192.[22].[1].[1]")

        # 测试包含的IP
        assert selector.matches("192.22.1.1")

        # 测试不包含的IP
        assert not selector.matches("192.23.1.1")
        assert not selector.matches("192.22.2.1")

        # 测试展开
        ips = selector.expand()
        assert ips == ["192.22.1.1"]

    def test_field_range_mixed(self):
        """测试字段范围混合表达式"""
        selector = IPSelector("192.[22:24,26].[1,3:5].1")

        # 测试包含的IP
        assert selector.matches("192.22.1.1")
        assert selector.matches("192.22.3.1")
        assert selector.matches("192.22.5.1")
        assert selector.matches("192.23.1.1")
        assert selector.matches("192.24.5.1")
        assert selector.matches("192.26.1.1")
        assert selector.matches("192.26.5.1")

        # 测试不包含的IP
        assert not selector.matches("192.21.1.1")
        assert not selector.matches("192.25.1.1")
        assert not selector.matches("192.22.2.1")
        assert not selector.matches("192.22.6.1")

        # 测试展开
        ips = selector.expand()
        assert len(ips) == 16  # (3+1) * (1+3) = 16

    def test_mixed_expressions(self):
        """测试混合表达式"""
        selector = IPSelector("192.168.1.0/30,10.0.0.1-10.0.0.3,172.[16:17].0.1")

        # 测试包含的IP
        assert selector.matches("192.168.1.0")
        assert selector.matches("192.168.1.3")
        assert selector.matches("10.0.0.1")
        assert selector.matches("10.0.0.3")
        assert selector.matches("172.16.0.1")
        assert selector.matches("172.17.0.1")

        # 测试不包含的IP
        assert not selector.matches("192.168.1.4")
        assert not selector.matches("10.0.0.4")
        assert not selector.matches("172.15.0.1")
        assert not selector.matches("172.18.0.1")

        # 测试展开
        ips = selector.expand()
        # CIDR 地址不包括网络和广播地址
        assert len(ips) == 7  # 2 (CIDR) + 3 (range) + 2 (field range) = 10

    def test_mixed_with_exclude(self):
        """测试混合表达式与排除"""
        selector = IPSelector("192.168.1.0/30,10.0.0.1-10.0.0.3 !192.168.1.1,10.0.0.2")

        # 测试包含的IP
        assert selector.matches("192.168.1.0")
        assert selector.matches("192.168.1.2")
        assert selector.matches("192.168.1.3")
        assert selector.matches("10.0.0.1")
        assert selector.matches("10.0.0.3")

        # 测试排除的IP
        assert not selector.matches("192.168.1.1")
        assert not selector.matches("10.0.0.2")

        # 测试展开
        ips = selector.expand()
        assert "192.168.1.1" not in ips
        assert "10.0.0.2" not in ips
        assert "192.168.1.2" in ips
        assert "10.0.0.1" in ips

    def test_invalid_ip(self):
        """测试无效IP"""
        selector = IPSelector("192.168.1.1")

        # 测试无效IP格式
        assert not selector.matches("256.168.1.1")
        assert not selector.matches("192.168.1")
        assert not selector.matches("192.168.1.1.1")
        assert not selector.matches("not.an.ip.address")

    def test_invalid_expression(self):
        """测试无效表达式"""
        # 测试无效CIDR
        with pytest.raises(ValueError):
            IPSelector("192.168.1.0/33")

        # 测试无效IP范围
        with pytest.raises(ValueError):
            IPSelector("192.168.1.300-192.168.1.1")

        # 测试无效字段范围
        with pytest.raises(ValueError):
            IPSelector("192.[22:266].1.1")

        # 测试无效IP字段
        with pytest.raises(ValueError):
            IPSelector("192.abc.1.1")

        # 测试无效字段范围表达式
        with pytest.raises(ValueError):
            IPSelector("192.[22:26].1")

    def test_whitespace_handling(self):
        """测试空格处理"""
        selector = IPSelector("  192.168.1.1 , 192.168.1.2  !  192.168.1.3  ")

        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.1.2")
        assert not selector.matches("192.168.1.3")

    def test_empty_expression(self):
        """测试空表达式"""
        selector = IPSelector("")

        assert not selector.matches("192.168.1.1")
        assert selector.expand() == []

    def test_expand_limit(self):
        """测试展开限制"""
        selector = IPSelector("192.168.1.0/24")

        # 测试限制为5
        ips = selector.expand(limit=5)
        assert len(ips) == 5

        # 测试限制为0
        ips = selector.expand(limit=0)
        assert len(ips) == 0

        # 测试限制为负数（应该使用默认值）
        ips = selector.expand(limit=-1)
        assert len(ips) == 254  # 默认限制

    def test_large_range(self):
        """测试大范围"""
        selector = IPSelector("192.168.1.0/16")

        # 测试展开限制
        ips = selector.expand(limit=1000)
        assert len(ips) == 1000

        # 测试匹配
        assert selector.matches("192.168.1.1")
        assert selector.matches("192.168.255.255")
        assert not selector.matches("192.169.0.1")

    def test_field_range_edge_cases(self):
        """测试字段范围边界情况"""
        # 测试0和255边界
        selector = IPSelector("[0:1].[0:1].[0:1].[0:1]")
        assert selector.matches("0.0.0.0")
        assert selector.matches("1.1.1.1")
        assert not selector.matches("2.2.2.2")

        # 测试单个字段范围
        selector = IPSelector("192.[0].[0].[0]")
        assert selector.matches("192.0.0.0")
        assert not selector.matches("192.0.0.1")

        # 测试最大字段范围
        selector = IPSelector("[0:255].[0:255].[0:255].[0:255]")
        assert selector.matches("0.0.0.0")
        assert selector.matches("255.255.255.255")

        # 测试展开限制
        selector = IPSelector("[0:255].[0:255].[0:255].[0:255]")
        ips = selector.expand(limit=1000)
        assert len(ips) == 1000

    def test_complex_expressions(self):
        """测试复杂表达式"""
        # 复杂混合表达式
        selector = IPSelector(
            "192.168.1.0/30,10.0.0.1-10.0.0.3,172.[16:17].0.1 !192.168.1.1,10.0.0.2"
        )

        # 测试包含的IP
        assert selector.matches("192.168.1.2")
        assert selector.matches("192.168.1.3")
        assert selector.matches("10.0.0.1")
        assert selector.matches("10.0.0.3")
        assert selector.matches("172.16.0.1")
        assert selector.matches("172.17.0.1")

        # 测试排除的IP
        assert not selector.matches("192.168.1.1")
        assert not selector.matches("10.0.0.2")

        # 测试展开
        ips = selector.expand()
        assert "192.168.1.1" not in ips
        assert "10.0.0.2" not in ips
        assert "10.0.0.1" in ips
        assert "172.16.0.1" in ips
        assert "172.17.0.1" in ips

    def test_performance(self):
        """测试性能"""
        import time

        # 大CIDR范围
        start_time = time.time()
        selector = IPSelector("10.0.0.0/8")
        ips = selector.expand(limit=10000)
        elapsed_time = time.time() - start_time

        assert len(ips) == 10000
        assert elapsed_time < 1.0  # 应该在1秒内完成

        # 大字段范围
        start_time = time.time()
        selector = IPSelector("10.[0:255].[0:255].[0:255]")
        ips = selector.expand(limit=10000)
        elapsed_time = time.time() - start_time

        assert len(ips) == 10000
        assert elapsed_time < 1.0  # 应该在1秒内完成

        # 复杂表达式
        start_time = time.time()
        selector = IPSelector(
            "10.0.0.0/8,172.[10:31].0.0,192.168.255.0/24 !10.0.0.1,172.16.0.1"
        )
        ips = selector.expand(limit=10000)
        elapsed_time = time.time() - start_time

        assert len(ips) == 10000
        assert elapsed_time < 1.0  # 应该在1秒内完成

    def test_ip_ordering(self):
        """测试IP排序"""
        selector = IPSelector("192.168.1.5,192.168.1.1,192.168.1.3")
        ips = selector.expand()

        # 应该按IP地址排序
        assert ips == ["192.168.1.1", "192.168.1.3", "192.168.1.5"]

        selector = IPSelector("192.168.2.1,192.168.1.1")
        ips = selector.expand()

        # 应该按IP地址排序
        assert ips == ["192.168.1.1", "192.168.2.1"]

    def test_duplicate_ips(self):
        """测试重复IP"""
        selector = IPSelector("192.168.1.1,192.168.1.1")
        ips = selector.expand()

        # 应该去重
        assert ips == ["192.168.1.1"]

        selector = IPSelector("192.168.1.0/30,192.168.1.1-192.168.1.3")
        ips = selector.expand()

        # 应该去重
        assert len(ips) == 3
        assert ips[0] == "192.168.1.1"
        assert ips[1] == "192.168.1.2"
        assert ips[2] == "192.168.1.3"
