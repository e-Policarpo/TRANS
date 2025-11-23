#!/usr/bin/env python3
"""
Script para Executar Testes do T.R.A.N.S.
Executa todos os testes unitários e de integração
"""

import subprocess
import sys
from pathlib import Path
import time


class TestRunner:
    """Runner para testes com relatórios"""
    
    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        self.results = {}
    
    def run_unit_tests(self):
        """Executa testes unitários"""
        print("="*80)
        print("EXECUTANDO TESTES UNITÁRIOS")
        print("="*80)
        print()
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "-v",
            "-m", "not integration and not slow and not ui",
            "--tb=short",
            "--color=yes"
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start
        
        self.results['unit'] = {
            'returncode': result.returncode,
            'duration': duration,
            'output': result.stdout + result.stderr
        }
        
        print(result.stdout)
        if result.returncode != 0:
            print("STDERR:", result.stderr)
        
        print(f"\nDuração: {duration:.2f}s")
        print()
        
        return result.returncode == 0
    
    def run_integration_tests(self):
        """Executa testes de integração"""
        print("="*80)
        print("EXECUTANDO TESTES DE INTEGRAÇÃO")
        print("="*80)
        print()
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "-v",
            "-m", "integration and not slow",
            "--tb=short",
            "--color=yes"
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start
        
        self.results['integration'] = {
            'returncode': result.returncode,
            'duration': duration,
            'output': result.stdout + result.stderr
        }
        
        print(result.stdout)
        if result.returncode != 0:
            print("STDERR:", result.stderr)
        
        print(f"\nDuração: {duration:.2f}s")
        print()
        
        return result.returncode == 0
    
    def run_slow_tests(self):
        """Executa testes lentos (opcional)"""
        print("="*80)
        print("EXECUTANDO TESTES LENTOS (PERFORMANCE)")
        print("="*80)
        print()
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "-v",
            "-m", "slow",
            "--tb=short",
            "--color=yes"
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start
        
        self.results['slow'] = {
            'returncode': result.returncode,
            'duration': duration,
            'output': result.stdout + result.stderr
        }
        
        print(result.stdout)
        if result.returncode != 0:
            print("STDERR:", result.stderr)
        
        print(f"\nDuração: {duration:.2f}s")
        print()
        
        return result.returncode == 0
    
    def run_coverage_analysis(self):
        """Executa análise de cobertura"""
        print("="*80)
        print("ANÁLISE DE COBERTURA DE CÓDIGO")
        print("="*80)
        print()
        
        cmd = [
            "pytest",
            str(self.test_dir),
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html",
            "-m", "not slow"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(result.stdout)
        print()
        
        return result.returncode == 0
    
    def generate_report(self, output_file: Path):
        """Gera relatório de testes"""
        report_lines = []
        
        report_lines.append("="*80)
        report_lines.append("RELATÓRIO DE TESTES - T.R.A.N.S. HyperSpec Analyzer")
        report_lines.append("="*80)
        report_lines.append("")
        
        # Sumário
        total_duration = sum(r['duration'] for r in self.results.values())
        passed_tests = sum(1 for r in self.results.values() if r['returncode'] == 0)
        total_tests = len(self.results)
        
        report_lines.append("📊 SUMÁRIO")
        report_lines.append("-"*80)
        report_lines.append(f"Total de suítes executadas: {total_tests}")
        report_lines.append(f"Suítes aprovadas: {passed_tests}/{total_tests}")
        report_lines.append(f"Tempo total: {total_duration:.2f}s")
        report_lines.append("")
        
        # Resultados por categoria
        for category, result in self.results.items():
            status = "✅ PASSOU" if result['returncode'] == 0 else "❌ FALHOU"
            report_lines.append(f"{'='*80}")
            report_lines.append(f"{category.upper()}: {status}")
            report_lines.append(f"Duração: {result['duration']:.2f}s")
            report_lines.append(f"{'='*80}")
            report_lines.append("")
            
            # Extrair estatísticas do output
            output = result['output']
            
            # Procurar por estatísticas do pytest
            if 'passed' in output:
                for line in output.split('\n'):
                    if 'passed' in line or 'failed' in line or 'error' in line:
                        report_lines.append(f"  {line.strip()}")
            
            report_lines.append("")
        
        # Salvar relatório
        report_content = '\n'.join(report_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(report_content)
        print(f"\nRelatório salvo em: {output_file}")
    
    def run_all(self, include_slow=False, include_coverage=False):
        """Executa todos os testes"""
        print("\n" + "="*80)
        print("INICIANDO BATERIA COMPLETA DE TESTES")
        print("="*80)
        print()
        
        # Testes unitários
        unit_passed = self.run_unit_tests()
        
        # Testes de integração
        integration_passed = self.run_integration_tests()
        
        # Testes lentos (opcional)
        if include_slow:
            slow_passed = self.run_slow_tests()
        
        # Cobertura (opcional)
        if include_coverage:
            self.run_coverage_analysis()
        
        # Gerar relatório
        report_file = Path("/mnt/user-data/outputs/RELATORIO_TESTES.md")
        self.generate_report(report_file)
        
        # Status final
        print("\n" + "="*80)
        print("RESULTADO FINAL")
        print("="*80)
        
        if unit_passed and integration_passed:
            print("✅ TODOS OS TESTES PASSARAM!")
            return 0
        else:
            print("❌ ALGUNS TESTES FALHARAM")
            if not unit_passed:
                print("  - Testes unitários: FALHOU")
            if not integration_passed:
                print("  - Testes de integração: FALHOU")
            return 1


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Executar testes do T.R.A.N.S.')
    parser.add_argument('--unit', action='store_true', help='Executar apenas testes unitários')
    parser.add_argument('--integration', action='store_true', help='Executar apenas testes de integração')
    parser.add_argument('--slow', action='store_true', help='Incluir testes lentos')
    parser.add_argument('--coverage', action='store_true', help='Gerar relatório de cobertura')
    parser.add_argument('--all', action='store_true', help='Executar todos os testes')
    
    args = parser.parse_args()
    
    test_dir = Path(__file__).parent / 'tests'
    runner = TestRunner(test_dir)
    
    if args.unit:
        success = runner.run_unit_tests()
        return 0 if success else 1
    
    elif args.integration:
        success = runner.run_integration_tests()
        return 0 if success else 1
    
    elif args.slow:
        success = runner.run_slow_tests()
        return 0 if success else 1
    
    elif args.coverage:
        success = runner.run_coverage_analysis()
        return 0 if success else 1
    
    else:  # Default: run all
        return runner.run_all(
            include_slow=args.slow,
            include_coverage=args.coverage
        )


if __name__ == '__main__':
    sys.exit(main())
