#!/usr/bin/env python3
"""SSH并行执行性能测试"""

import asyncio
import time
import statistics
from pathlib import Path
import json
import argparse
from typing import List

# 假设pypssh已安装
from pypssh.core.executor import SSHExecutor
from pypssh.core.models import ConnectionConfig
from pypssh.selector.ip_selector import IPSelector
from pypssh.selector.label_selector import LabelSelector, models.Host
from pypssh.ui.progress import ProgressDisplay, create_progress_callback

class PerformanceTest:
    """性能测试类"""
    
    def __init__(self, base_port: int = 2001, max_servers: int = 1000):
        self.base_port = base_port
        self.max_servers = max_servers
        self.results = {}
    
    def generate_configs(self, count: int) -> List[ConnectionConfig]:
        """生成测试连接配置"""
        configs = []
        
        for i in range(count):
            config = ConnectionConfig(
                host='localhost',
                port=self.base_port + i,
                username='testuser',
                password='testpassword',
                connect_timeout=5.0,
                command_timeout=10.0,
                labels={
                    'id': f"{i+1:06d}",
                    'env': 'prod' if (i+1) % 3 == 0 else 'test',
                    'tier': 'web' if (i+1) % 4 == 0 else 'db' if (i+1) % 4 == 1 else 'cache',
                    'region': 'asia' if (i+1) % 2 == 0 else 'us',
                    'zone': f'zone-{(i+1) % 5 + 1}',
                }
            )
            configs.append(config)
        
        return configs
    
    async def test_concurrent_execution(
        self, 
        configs: List[ConnectionConfig], 
        command: str,
        max_concurrent: int = 50
    ):
        """测试并发执行性能"""
        
        display = ProgressDisplay()
        progress_callback = create_progress_callback(display)
        
        executor = SSHExecutor(
            max_concurrent=max_concurrent,
            progress_callback=progress_callback
        )
        
        display.start_execution(len(configs), command)
        
        start_time = time.time()
        results = await executor.execute_parallel(configs, command)
        end_time = time.time()
        
        display.finish_execution()
        
        # 统计结果
        execution_times = [r.execution_time for r in results if r.execution_time > 0]
        
        stats = {
            'total_hosts': len(configs),
            'max_concurrent': max_concurrent,
            'total_time': end_time - start_time,
            'success_count': len([r for r in results if r.exit_code == 0]),
            'error_count': len([r for r in results if r.exit_code != 0]),
            'avg_execution_time': statistics.mean(execution_times) if execution_times else 0,
            'median_execution_time': statistics.median(execution_times) if execution_times else 0,
            'min_execution_time': min(execution_times) if execution_times else 0,
            'max_execution_time': max(execution_times) if execution_times else 0,
            'throughput': len(configs) / (end_time - start_time),
        }
        
        return stats, results
    
    async def run_scale_test(self, command: str = "echo 'Hello World'"):
        """运行规模测试"""
        test_scales = [10, 50, 100, 500, 1000]
        concurrent_limits = [10, 25, 50, 100]
        
        print("Starting scale performance tests...")
        
        for scale in test_scales:
            if scale > self.max_servers:
                continue
                
            configs = self.generate_configs(scale)
            
            for concurrent in concurrent_limits:
                if concurrent > scale:
                    continue
                    
                print(f"\nTesting {scale} hosts with {concurrent} concurrent connections...")
                
                try:
                    stats, _ = await self.test_concurrent_execution(
                        configs, command, concurrent
                    )
                    
                    test_key = f"{scale}_{concurrent}"
                    self.results[test_key] = stats
                    
                    print(f"Completed in {stats['total_time']:.2f}s, "
                          f"throughput: {stats['throughput']:.1f} hosts/s")
                    
                except Exception as e:
                    print(f"Test failed: {e}")
                
                # 等待一段时间再进行下一个测试
                await asyncio.sleep(2)
    
    async def test_selectors(self):
        """测试选择器性能"""
        print("\nTesting selectors performance...")
        
        configs = self.generate_configs(1000)
        servers = [
            models.Host(
                host=config.host,
                port=config.port,
                username=config.username,
                labels=config.labels
            )
            for config in configs
        ]
        
        # IP选择器测试
        ip_selector = IPSelector("127.0.0.1")
        start_time = time.time()
        selected = [s for s in servers if ip_selector.matches(s.host)]
        ip_time = time.time() - start_time
        
        print(f"IP selector: selected {len(selected)} from {len(servers)} in {ip_time*1000:.2f}ms")
        
        # 标签选择器测试
        label_selector = LabelSelector("env=prod,tier=web")
        start_time = time.time()
        selected = [s for s in servers if label_selector.matches(s)]
        label_time = time.time() - start_time
        
        print(f"Label selector: selected {len(selected)} from {len(servers)} in {label_time*1000:.2f}ms")
    
    def save_results(self, filename: str = "performance_results.json"):
        """保存测试结果"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Results saved to {filename}")

async def main():
    parser = argparse.ArgumentParser(description="SSH Performance Testing")
    parser.add_argument('--max-servers', type=int, default=1000, help='Maximum number of servers to test')
    parser.add_argument('--base-port', type=int, default=2001, help='Base port for SSH connections')
    parser.add_argument('--command', type=str, default="echo 'Hello World'", help='Command to execute')
    
    args = parser.parse_args()
    
    test = PerformanceTest(args.base_port, args.max_servers)
    
    # 运行规模测试
    await test.run_scale_test(args.command)
    
    # 测试选择器性能
    await test.test_selectors()
    
    # 保存结果
    test.save_results()

if __name__ == "__main__":
    asyncio.run(main())