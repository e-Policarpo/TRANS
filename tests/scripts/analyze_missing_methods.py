#!/usr/bin/env python3
"""
Análise de métodos faltantes no main_window.py
Compara métodos chamados vs métodos implementados
"""

import re
from pathlib import Path
from collections import defaultdict

def extract_method_calls(content):
    """Extrai todas as chamadas de método self.método()"""
    pattern = r'self\.(\w+)\('
    calls = re.findall(pattern, content)
    return set(calls)

def extract_method_definitions(content):
    """Extrai todas as definições de método def método("""
    pattern = r'def (\w+)\('
    definitions = re.findall(pattern, content)
    return set(definitions)

def analyze_file(filepath):
    """Analisa um arquivo Python"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    calls = extract_method_calls(content)
    definitions = extract_method_definitions(content)
    
    # Métodos chamados mas não definidos
    missing = calls - definitions
    
    # Remover métodos herdados do Qt
    qt_methods = {
        'setWindowTitle', 'setGeometry', 'setCentralWidget', 'menuBar',
        'addToolBar', 'statusBar', 'close', 'setWindowIcon', 'setAttribute',
        'addAction', 'addMenu', 'addSeparator', 'addWidget', 'addLayout',
        'setLayout', 'setMinimumWidth', 'setMaximumWidth', 'setEnabled',
        'setText', 'setChecked', 'setRange', 'setValue', 'value', 'isChecked',
        'currentText', 'currentIndex', 'setCurrentIndex', 'clear', 'addItems',
        'addItem', 'show', 'hide', 'setVisible', 'append', 'toPlainText',
        'scrollToTop', 'exec', 'accept', 'reject', 'showMessage', 'clearMessage',
        'exists', 'name', 'parent', 'stem', 'suffix', 'is_dir', 'glob',
        'setRowCount', 'setColumnCount', 'setHorizontalHeaderLabels', 'setItem',
        'getSaveFileName', 'getOpenFileName', 'getExistingDirectory',
        'information', 'warning', 'critical', 'about', 'addPermanentWidget',
        'setStyleSheet', 'setToolTip', 'clicked', 'connect', 'triggered',
        'verticalScrollBar', 'maximum', 'addTab', 'removeTab', 'setTabText',
        'setTabEnabled', 'widget', 'indexOf', 'setSizes', 'count',
        'setParent', 'itemAt', 'takeItem', 'raise_', 'activateWindow',
        'fill', 'drawEllipse', 'setBrush', 'setPen', 'setFont', 'drawText',
        'end', 'setRenderHint', 'rect', 'setModal', 'currentRow',
    }
    
    missing = missing - qt_methods
    
    # Remover propriedades e atributos conhecidos
    properties = {
        'data', 'metadata', 'shape', 'spectra', 'columns', 'values', 'iloc',
        'independent_var', 'topography', 'selected_blocks', 'discretized_data',
        'block_size', 'num_spectra', 'num_points', 'independent_var_name',
    }
    
    missing = missing - properties
    
    return {
        'calls': calls,
        'definitions': definitions,
        'missing': missing
    }

def find_method_locations(filepath, method_name):
    """Encontra as linhas onde um método é chamado"""
    locations = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if f'self.{method_name}(' in line:
                locations.append((i, line.strip()))
    return locations

def main():
    # Métodos herdados do Qt (definição global para uso em todo main)
    qt_methods = {
        'setWindowTitle', 'setGeometry', 'setCentralWidget', 'menuBar',
        'addToolBar', 'statusBar', 'close', 'setWindowIcon', 'setAttribute',
        'addAction', 'addMenu', 'addSeparator', 'addWidget', 'addLayout',
        'setLayout', 'setMinimumWidth', 'setMaximumWidth', 'setEnabled',
        'setText', 'setChecked', 'setRange', 'setValue', 'value', 'isChecked',
        'currentText', 'currentIndex', 'setCurrentIndex', 'clear', 'addItems',
        'addItem', 'show', 'hide', 'setVisible', 'append', 'toPlainText',
        'scrollToTop', 'exec', 'accept', 'reject', 'showMessage', 'clearMessage',
        'exists', 'name', 'parent', 'stem', 'suffix', 'is_dir', 'glob',
        'setRowCount', 'setColumnCount', 'setHorizontalHeaderLabels', 'setItem',
        'getSaveFileName', 'getOpenFileName', 'getExistingDirectory',
        'information', 'warning', 'critical', 'about', 'addPermanentWidget',
        'setStyleSheet', 'setToolTip', 'clicked', 'connect', 'triggered',
        'verticalScrollBar', 'maximum', 'addTab', 'removeTab', 'setTabText',
        'setTabEnabled', 'widget', 'indexOf', 'setSizes', 'count',
        'setParent', 'itemAt', 'takeItem', 'raise_', 'activateWindow',
        'fill', 'drawEllipse', 'setBrush', 'setPen', 'setFont', 'drawText',
        'end', 'setRenderHint', 'rect', 'setModal', 'currentRow', 'format',
    }
    
    # Analisar main_window.py
    main_window_path = Path('/mnt/user-data/uploads/main_window.py')
    deepseek_path = Path('/mnt/user-data/uploads/deepseek_python_20251121_9d93f0.py')
    
    print("="*80)
    print("ANÁLISE DE MÉTODOS FALTANTES - main_window.py")
    print("="*80)
    print()
    
    # Analisar arquivo atual
    result = analyze_file(main_window_path)
    
    print(f"Total de métodos chamados: {len(result['calls'])}")
    print(f"Total de métodos definidos: {len(result['definitions'])}")
    print(f"Métodos faltantes: {len(result['missing'])}")
    print()
    
    if result['missing']:
        print("MÉTODOS CHAMADOS MAS NÃO IMPLEMENTADOS:")
        print("-" * 80)
        
        for method in sorted(result['missing']):
            locations = find_method_locations(main_window_path, method)
            print(f"\n❌ {method}()")
            print(f"   Chamado em {len(locations)} locais:")
            for line_num, line in locations[:5]:  # Mostrar até 5 localizações
                print(f"      Linha {line_num}: {line[:70]}...")
            if len(locations) > 5:
                print(f"      ... e mais {len(locations) - 5} locais")
    
    # Comparar com versão Deepseek
    print("\n" + "="*80)
    print("COMPARAÇÃO COM VERSÃO DEEPSEEK")
    print("="*80)
    print()
    
    deepseek_result = analyze_file(deepseek_path)
    
    # Métodos que existem no Deepseek mas não na versão atual
    in_deepseek = deepseek_result['definitions'] - result['definitions']
    
    # Filtrar apenas métodos relevantes (não começam com _ e não são Qt)
    relevant = {m for m in in_deepseek if not m.startswith('_') and m not in qt_methods}
    
    if relevant:
        print("MÉTODOS PRESENTES NO DEEPSEEK MAS AUSENTES NA VERSÃO ATUAL:")
        print("-" * 80)
        for method in sorted(relevant):
            # Verificar se é chamado na versão atual
            if method in result['calls']:
                print(f"⚠️  {method}() - CHAMADO mas não implementado!")
            else:
                print(f"ℹ️  {method}() - Não usado na versão atual")
    
    # Estatísticas finais
    print("\n" + "="*80)
    print("ESTATÍSTICAS")
    print("="*80)
    print(f"Versão atual:")
    print(f"  - Métodos definidos: {len(result['definitions'])}")
    print(f"  - Métodos chamados: {len(result['calls'])}")
    print(f"  - Métodos faltantes: {len(result['missing'])}")
    print()
    print(f"Versão Deepseek:")
    print(f"  - Métodos definidos: {len(deepseek_result['definitions'])}")
    print(f"  - Métodos chamados: {len(deepseek_result['calls'])}")
    print(f"  - Métodos faltantes: {len(deepseek_result['missing'])}")

if __name__ == '__main__':
    main()
