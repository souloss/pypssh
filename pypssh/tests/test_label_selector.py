import pytest
from typing import Dict, List, Any, Callable, Set
from dataclasses import dataclass
from pypssh.selector.label_selector import LabelSelector, select_servers
from pypssh.core import models

class TestLabelSelector:
    """测试 LabelSelector 类"""

    @pytest.fixture
    def sample_servers(self) ->List[models.Host]:
        """创建测试用的服务器列表"""
        return [
            models.Host(
                host="192.168.1.1",
                labels={"env": "prod", "tier": "web", "region": "us-east"},
            ),  # 0
            models.Host(
                host="192.168.1.2",
                labels={"env": "dev", "tier": "db", "region": "us-west"},
            ),  # 1
            models.Host(
                host="192.168.1.3",
                labels={"env": "staging", "tier": "web", "region": "us-east"},
            ),  # 2
            models.Host(
                host="192.168.1.4",
                labels={"env": "prod", "tier": "api", "region": "eu-west"},
            ),  # 3
            models.Host(
                host="192.168.1.5",
                labels={"env": "test", "tier": "worker", "replicas": "3"},
            ),  # 4
            models.Host(
                host="192.168.1.6",
                labels={"env": "prod", "tier": "web", "name": "web-server-01"},
            ),  # 5
            models.Host(
                host="192.168.1.7",
                labels={"env": "prod", "tier": "db", "backup": "true"},
            ),  # 6
            models.Host(
                host="192.168.1.8", labels={"env": "dev", "tier": "web", "temp": "true"}
            ),  # 7
        ]

    # 测试等值操作符
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("env=prod", [0, 3, 5, 6]),  # 修正：索引5的env也是prod
            ("tier=web", [0, 2, 5, 7]),  # 所有tier=web的服务器
            ("region=us-east", [0, 2]),  # region=us-east的服务器
            ("nonexistent=value", []),  # 不存在的键值对
        ],
    )
    def test_equality_operator(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i for i, server in enumerate(sample_servers) if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试不等值操作符
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("env!=prod", [1, 2, 4, 7]),  # env不是prod的服务器
            ("tier!=web", [1, 3, 4, 6]),  # tier不是web的服务器
            ("region!=us-east", [1, 3, 4, 5, 6, 7]),  # region不是us-east的服务器
        ],
    )
    def test_inequality_operator(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试存在性函数
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("has(backup)", [6]),  # 有backup标签的服务器
            ("has(temp)", [7]),  # 有temp标签的服务器
            ("has(nonexistent)", []),  # 不存在的标签
            ("!has(backup)", [0, 1, 2, 3, 4, 5, 7]),  # 没有backup标签的服务器
            ("!has(temp)", [0, 1, 2, 3, 4, 5, 6]),  # 没有temp标签的服务器
        ],
    )
    def test_existence_function(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试集合操作
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("env in (prod,staging)", [0, 2, 3, 5, 6]),  # env在prod或staging中的服务器
            ("tier in (web,api)", [0, 2, 3, 5, 7]),  # tier在web或api中的服务器
            ("env notin (dev,test)", [0, 2, 3, 5, 6]),  # env不在dev或test中的服务器
            ("tier notin (db,worker)", [0, 2, 3, 5, 7]),  # tier不在db或worker中的服务器
        ],
    )
    def test_set_operators(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试数值比较操作符
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("count(replicas) > 2", [4]),  # replicas数量大于2的服务器
            ("count(replicas) >= 3", [4]),  # replicas数量大于等于3的服务器
            ("count(replicas) < 4", [0, 1, 2, 3, 4, 5, 6, 7]),  # replicas数量小于4的服务器
            (
                "count(replicas) <= 3",
                [0, 1, 2, 3, 4, 5, 6, 7],
            ),  # replicas数量小于等于3的服务器
        ],
    )
    def test_numeric_operators(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试字符串函数
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ('startswith(name, "web-")', [5]),  # name以"web-"开头的服务器
            ('endswith(name, "-01")', [5]),  # name以"-01"结尾的服务器
            ('contains(region, "us")', [0, 1, 2]),  # region包含"us"的服务器
            ("len(name) > 10", [5]),  # name长度大于10的服务器
            ('regex(name, "web-server-\\d+")', [5]),  # name匹配正则表达式的服务器
        ],
    )
    def test_string_functions(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试组合条件（AND逻辑）
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("env=prod, tier=web", [0, 5]),  # env=prod且tier=web的服务器
            ("env=prod, region=us-east", [0]),  # env=prod且region=us-east的服务器
            ("tier=web, has(temp)", [7]),  # tier=web且有temp标签的服务器
            ("env=staging, tier=web, region=us-east", [2]),  # 所有条件都满足的服务器
        ],
    )
    def test_combined_conditions(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试无效表达式
    @pytest.mark.parametrize(
        "expression",
        [
            "invalid_function()",
            "env=",  # 缺少值
            "=value",  # 缺少键
            "env in ()",  # 空集合
            "env in (prod",  # 括号不匹配
            "count()",  # 缺少参数
            "has(,)",  # 无效参数
            "env > string",  # 数值比较与非数值
        ],
    )
    def test_invalid_expressions(self, expression, sample_servers):
        selector = LabelSelector(expression)
        # 无效表达式应该不匹配任何服务器
        for server in sample_servers:
            assert not selector.matches(server.labels)

    # 测试空表达式
    def test_empty_expression(self, sample_servers):
        selector = LabelSelector("")
        # 空表达式应该匹配所有服务器
        for i, server in enumerate(sample_servers):
            assert selector.matches(server)

    # 测试只有空格的表达式
    def test_whitespace_expression(self, sample_servers):
        selector = LabelSelector("   ,   ,   ")
        # 只有空格的表达式应该匹配所有服务器
        for i, server in enumerate(sample_servers):
            assert selector.matches(server.labels)

    # 测试复杂的嵌套否定
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            (
                "!has(backup), !has(temp)",
                [0, 1, 2, 3, 4, 5],
            ),  # 既没有backup也没有temp标签的服务器
            ("env!=prod, !has(temp)", [1, 2, 4]),  # env不是prod且没有temp标签的服务器
            ("!(env=prod), tier=web", [2, 7]),  # env不是prod且tier=web的服务器
        ],
    )
    def test_complex_negations(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试数值比较的边界情况
    def test_numeric_comparison_edge_cases(self, sample_servers):
        # 测试非数值标签
        selector = LabelSelector("env > 100")
        for server in sample_servers:
            assert not selector.matches(server.labels)  # 字符串比较应该返回False

        # 测试缺失标签
        selector = LabelSelector("nonexistent > 0")
        for server in sample_servers:
            assert not selector.matches(server.labels)

    # 测试函数调用的错误处理
    def test_function_error_handling(self, sample_servers):
        # 测试无效的正则表达式
        selector = LabelSelector('regex(name, "[invalid")')
        for server in sample_servers:
            assert not selector.matches(server.labels)

        # 测试参数不足
        selector = LabelSelector("startswith(name)")
        for server in sample_servers:
            assert not selector.matches(server.labels)

    # 测试集合操作的各种格式
    @pytest.mark.parametrize(
        "expression, expected_matches",
        [
            ("env in (prod, staging)", [0, 2, 3, 5, 6]),
            ("env in (prod,staging)", [0, 2, 3, 5, 6]),  # 无空格
            ("env in( prod, staging )", [0, 2, 3, 5, 6]),  # 混合空格
            ("env in  (prod, staging)", [0, 2, 3, 5, 6]),  # 多空格
        ],
    )
    def test_set_operator_formats(self, expression, expected_matches, sample_servers):
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == expected_matches

    # 测试操作符优先级
    def test_operator_precedence(self, sample_servers):
        # 测试逗号（AND）优先级高于否定
        selector = LabelSelector("!env=prod, tier=web")
        # 应该解释为 (!env=prod) AND (tier=web)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == [2, 7]  # 不是prod且是web的服务器

    # 测试长表达式
    def test_long_expression(self, sample_servers):
        expression = "env=prod, tier=web, region=us-east, !has(temp), !has(backup)"
        selector = LabelSelector(expression)
        matches = [
            i
            for i, server in enumerate(sample_servers)
            if selector.matches(server.labels)
        ]
        assert matches == [0]  # 只有第一个服务器匹配所有条件

    # 测试特殊字符处理
    def test_special_characters(self, sample_servers):
        # 添加带特殊字符的服务器
        server = models.Host(
            host="192.168.1.9", labels={"key": "value,with,commas", "special": "test@#"}
        )
        sample_servers.append(server)

        # 测试包含逗号的值
        selector = LabelSelector('key="value,with,commas"')
        assert selector.matches(server.labels)

        # 测试特殊字符
        selector = LabelSelector("special=test@#")
        assert selector.matches(server.labels)


class TestSelectServers:
    """测试 select_servers 函数"""

    @pytest.fixture
    def sample_servers(self):
        """创建测试用的服务器列表"""
        return [
            models.Host(host="192.168.1.1", labels={"env": "prod", "tier": "web"}),
            models.Host(host="192.168.1.2", labels={"env": "dev", "tier": "db"}),
            models.Host(host="192.168.1.10", labels={"env": "prod", "tier": "web"}),
            models.Host(host="192.168.1.20", labels={"env": "test", "tier": "worker"}),
        ]

    # 测试仅使用IP表达式
    def test_ip_expression_only(self, sample_servers):
        result = select_servers(sample_servers, ip_expr="192.168.1.1-192.168.1.10")
        expected_hosts = ["192.168.1.1", "192.168.1.2", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试仅使用标签表达式
    def test_label_expression_only(self, sample_servers):
        result = select_servers(sample_servers, label_expr="env=prod")
        expected_hosts = ["192.168.1.1", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试同时使用IP和标签表达式
    def test_both_expressions(self, sample_servers):
        result = select_servers(
            sample_servers,
            ip_expr="192.168.1.1-192.168.1.20",
            label_expr="env=prod, tier=web",
        )
        expected_hosts = ["192.168.1.1", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试无表达式
    def test_no_expressions(self, sample_servers):
        result = select_servers(sample_servers)
        assert len(result) == len(sample_servers)
        assert [s.host for s in result] == [s.host for s in sample_servers]

    # 测试空表达式
    def test_empty_expressions(self, sample_servers):
        result = select_servers(sample_servers, ip_expr="", label_expr="")
        assert len(result) == len(sample_servers)

    # 测试不匹配任何服务器的表达式
    def test_no_matches(self, sample_servers):
        result = select_servers(
            sample_servers, ip_expr="10.0.0.1", label_expr="nonexistent=value"
        )
        assert len(result) == 0

    # 测试复杂表达式组合
    def test_complex_expressions(self, sample_servers):
        result = select_servers(
            sample_servers,
            ip_expr="192.168.1.[1:10]",
            label_expr="env in (prod,dev), tier!=worker",
        )
        expected_hosts = ["192.168.1.1", "192.168.1.2", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试IP表达式过滤掉所有服务器
    def test_ip_filters_all(self, sample_servers):
        result = select_servers(
            sample_servers, ip_expr="10.0.0.1", label_expr="env=prod"
        )
        assert len(result) == 0

    # 测试标签表达式过滤掉所有服务器
    def test_label_filters_all(self, sample_servers):
        result = select_servers(
            sample_servers, ip_expr="192.168.1.1", label_expr="nonexistent=value"
        )
        assert len(result) == 0

    # 测试服务器列表为空
    def test_empty_server_list(self):
        result = select_servers([], ip_expr="192.168.1.1", label_expr="env=prod")
        assert len(result) == 0

    # 测试无效IP表达式
    def test_invalid_ip_expression(self, sample_servers):
        # 无效IP表达式应该抛出异常
        with pytest.raises(Exception):
            select_servers(sample_servers, ip_expr="invalid_ip")

    # 测试无效标签表达式
    def test_invalid_label_expression(self, sample_servers):
        # 无效标签表达式应该不匹配任何服务器
        result = select_servers(sample_servers, label_expr="invalid_expression()")
        assert len(result) == 0

    # 测试部分匹配
    def test_partial_matches(self, sample_servers):
        result = select_servers(
            sample_servers, ip_expr="192.168.1.[1:20]", label_expr="env=prod"
        )
        expected_hosts = ["192.168.1.1", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试否定条件
    def test_negation_conditions(self, sample_servers):
        result = select_servers(
            sample_servers, label_expr="env!=test, !has(nonexistent)"
        )
        expected_hosts = ["192.168.1.1", "192.168.1.2", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts

    # 测试函数调用
    def test_function_calls(self, sample_servers):
        # 添加一个带数值标签的服务器
        sample_servers.append(models.Host(host="192.168.1.30", labels={"count": "5"}))

        result = select_servers(sample_servers, label_expr="count(count) > 3")
        expected_hosts = ["192.168.1.30"]
        assert [s.host for s in result] == expected_hosts

    # 测试大小写敏感
    def test_case_sensitivity(self, sample_servers):
        # 添加大小写混合标签
        sample_servers.append(models.Host(host="192.168.1.40", labels={"Env": "Prod"}))

        # 默认应该是大小写敏感的
        result = select_servers(sample_servers, label_expr="env=Prod")
        assert len(result) == 0

        result = select_servers(sample_servers, label_expr="Env=Prod")
        assert [s.host for s in result] == ["192.168.1.40"]

    # 测试性能（大列表）
    def test_performance_large_list(self):
        # 创建大量服务器
        servers = [
            models.Host(
                host=f"192.168.1.{i}", labels={"env": "prod" if i % 2 == 0 else "dev"}
            )
            for i in range(1000)
        ]

        import time

        start_time = time.time()
        result = select_servers(
            servers, ip_expr="192.168.1.[100:200]", label_expr="env=prod"
        )
        elapsed_time = time.time() - start_time

        # 应该快速返回
        assert elapsed_time < 1.0
        # 检查结果数量
        assert len(result) == 51  # 100-200之间有101个IP，其中一半是prod

    # 测试边界IP范围
    def test_boundary_ip_range(self, sample_servers):
        result = select_servers(sample_servers, ip_expr="192.168.1.1-192.168.1.1")
        expected_hosts = ["192.168.1.1"]
        assert [s.host for s in result] == expected_hosts

    # 测试重叠条件
    def test_overlapping_conditions(self, sample_servers):
        result = select_servers(
            sample_servers,
            ip_expr="192.168.1.1-192.168.1.20",
            label_expr="env=prod, tier in (web,db)",
        )
        expected_hosts = ["192.168.1.1", "192.168.1.10"]
        assert [s.host for s in result] == expected_hosts
