#!/usr/bin/env python3
"""
Análise de conexões de botões e slots
Verifica se todos os métodos conectados a botões estão implementados
"""

import re
from pathlib import Path

def extract_button_connections(content):
    """Extrai conexões de botões/actions com seus métodos"""
    # Padrões para diferentes tipos de conexões
    patterns = [
        r'\.clicked\.connect\(self\.(\w+)\)',
        r'\.triggered\.connect\(self\.(\w+)\)',
        r'\.connect\(self\.(\w+)\)',
    ]
    
    connections = {}
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        for pattern in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                method_name = match.group(1)
                if method_name not in connections:
                    connections[method_name] = []
                connections[method_name].append((i, line.strip()))
    
    return connections

def extract_method_definitions(content):
    """Extrai definições de métodos"""
    pattern = r'def (\w+)\('
    definitions = re.findall(pattern, content)
    return set(definitions)

def analyze_ui_connections():
    """Analisa conexões da UI"""
    main_window_path = Path('/mnt/user-data/uploads/main_window.py')
    
    with open(main_window_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    connections = extract_button_connections(content)
    definitions = extract_method_definitions(content)
    
    print("="*80)
    print("ANÁLISE DE CONEXÕES DE BOTÕES/ACTIONS")
    print("="*80)
    print()
    
    print(f"Total de conexões encontradas: {len(connections)}")
    print(f"Total de métodos definidos: {len(definitions)}")
    print()
    
    # Verificar quais métodos conectados não estão implementados
    missing = set(connections.keys()) - definitions
    
    if missing:
        print("❌ MÉTODOS CONECTADOS MAS NÃO IMPLEMENTADOS:")
        print("-" * 80)
        for method in sorted(missing):
            print(f"\n{method}()")
            for line_num, line in connections[method]:
                print(f"  Linha {line_num}: {line[:75]}...")
    else:
        print("✅ Todos os métodos conectados estão implementados!")
    
    # Listar todas as conexões
    print("\n" + "="*80)
    print("TODAS AS CONEXÕES UI -> MÉTODOS")
    print("="*80)
    print()
    
    for method in sorted(connections.keys()):
        status = "✅" if method in definitions else "❌"
        print(f"{status} {method}()")
        for line_num, line in connections[method][:2]:  # Mostrar até 2 exemplos
            # Extrair o nome do widget/botão
            widget_match = re.search(r'self\.(\w+)\.(clicked|triggered)', line)
            if widget_match:
                widget_name = widget_match.group(1)
                print(f"      Widget: {widget_name}")
    
    # Análise de métodos chamados em callbacks
    print("\n" + "="*80)
    print("ANÁLISE DE MÉTODOS CHAMADOS DENTRO DOS CALLBACKS")
    print("="*80)
    print()
    
    # Extrair corpo de cada método implementado
    for method in sorted(definitions):
        if method in connections:  # É um callback conectado
            # Encontrar o corpo do método
            pattern = rf'def {method}\(.*?\):(.*?)(?=\n    def |\n\nclass |\Z)'
            matches = re.finditer(pattern, content, re.DOTALL)
            
            for match in matches:
                body = match.group(1)
                # Procurar por chamadas de outros métodos
                called_methods = set(re.findall(r'self\.(\w+)\(', body))
                
                # Remover métodos do Qt e propriedades
                qt_methods = {'setText', 'isChecked', 'value', 'setValue', 'show', 
                            'hide', 'setVisible', 'currentText', 'warning', 'information',
                            'critical', 'getSaveFileName', 'getExistingDirectory',
                            'showMessage', 'clearMessage', 'append', 'clear',
                            'verticalScrollBar', 'maximum', 'toPlainText', 'setCurrentIndex'}
                
                called_methods = called_methods - qt_methods - {'data', 'metadata', 
                                                                'spectra', 'topography'}
                
                # Verificar quais métodos chamados não estão implementados
                missing_called = called_methods - definitions
                
                if missing_called:
                    print(f"\n⚠️  {method}() chama métodos não implementados:")
                    for m in sorted(missing_called):
                        print(f"      - {m}()")

def check_specific_methods():
    """Verifica métodos específicos que são problemáticos"""
    main_window_path = Path('/mnt/user-data/uploads/main_window.py')
    
    print("\n" + "="*80)
    print("VERIFICAÇÃO DE MÉTODOS ESPECÍFICOS")
    print("="*80)
    print()
    
    # Métodos que são frequentemente necessários mas podem estar faltando
    critical_methods = [
        'export_iv_data',
        'export_derivatives', 
        'truncate_range',
        'generate_maps',
        'discretize_data',
    ]
    
    with open(main_window_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    definitions = extract_method_definitions(content)
    
    for method in critical_methods:
        status = "✅" if method in definitions else "❌"
        print(f"{status} {method}()")
        
        # Verificar se é chamado ou conectado
        if method not in definitions:
            # Verificar se aparece no código
            if f'self.{method}(' in content:
                print(f"      ⚠️  Método é CHAMADO mas não está implementado!")
            if f'connect(self.{method})' in content:
                print(f"      ⚠️  Método está CONECTADO a um botão mas não está implementado!")

if __name__ == '__main__':
    analyze_ui_connections()
    check_specific_methods()
