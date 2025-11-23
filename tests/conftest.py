"""
Configuração de testes para T.R.A.N.S. HyperSpec Analyzer
Fixtures e configurações compartilhadas para todos os testes
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import shutil

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from models.spectral_data import SpectralData, SpectralMetadata
from models.topography_data import TopographyData, TopographyMetadata


# ============================================================================
# FIXTURES - DADOS DE TESTE
# ============================================================================

@pytest.fixture
def sample_voltage_array():
    """Array de voltagem de teste"""
    return np.linspace(-2.0, 2.0, 100)


@pytest.fixture
def sample_current_array():
    """Array de corrente de teste (I-V)"""
    # Simula uma curva I-V típica
    V = np.linspace(-2.0, 2.0, 100)
    I = 1e-9 * np.tanh(V / 0.5) + 1e-10 * V  # Comportamento não-linear + componente linear
    return I


@pytest.fixture
def sample_spectral_dataframe(sample_voltage_array, sample_current_array):
    """DataFrame de teste para SpectralData"""
    n_spectra = 25  # 5x5 grid
    
    data = {'V': sample_voltage_array}
    
    for i in range(n_spectra):
        # Adiciona pequena variação aleatória
        noise = np.random.normal(0, 1e-11, len(sample_voltage_array))
        data[f'Spectrum_{i+1}'] = sample_current_array + noise
    
    return pd.DataFrame(data)


@pytest.fixture
def sample_spectral_metadata():
    """Metadata de teste para SpectralData"""
    return SpectralMetadata(
        source_type='test',
        dimensions=(5, 5),
        scan_mode='meander',
        units={'independent': 'V', 'dependent': 'A', 'x': 'nm', 'y': 'nm'},
        acquisition_date='2025-01-21',
        additional_info={'test': True}
    )


@pytest.fixture
def sample_spectral_data(sample_spectral_dataframe, sample_spectral_metadata):
    """SpectralData completo de teste"""
    return SpectralData(sample_spectral_dataframe, sample_spectral_metadata)


@pytest.fixture
def sample_topography_array():
    """Array 2D de topografia de teste"""
    # Cria uma superfície com gradiente e rugosidade
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 10, 50)
    X, Y = np.meshgrid(x, y)
    
    # Gradiente + ondulação + ruído
    Z = 0.5 * X + 0.3 * Y + 2 * np.sin(X) * np.cos(Y) + np.random.normal(0, 0.1, X.shape)
    
    return Z


@pytest.fixture
def sample_topography_metadata():
    """Metadata de teste para TopographyData"""
    return TopographyMetadata(
        dimensions=(50, 50),
        physical_size=(1000.0, 1000.0),  # 1000 nm x 1000 nm
        units='nm',
        scan_mode='raster'
    )


@pytest.fixture
def sample_topography_data(sample_topography_array, sample_topography_metadata):
    """TopographyData completo de teste"""
    return TopographyData(sample_topography_array, sample_topography_metadata)


@pytest.fixture
def temp_directory():
    """Diretório temporário para testes de I/O"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_nid_file_structure(temp_directory):
    """Estrutura de arquivos .nid de teste"""
    # Cria estrutura de diretório simulando dados Nanosurf
    data_dir = temp_directory / "sts_data"
    data_dir.mkdir()
    
    # Criar arquivos dummy .nid
    for i in range(5):
        nid_file = data_dir / f"spectrum_{i:03d}.nid"
        nid_file.touch()
    
    return data_dir


@pytest.fixture
def sample_neaspec_file_structure(temp_directory):
    """Estrutura de arquivos NeaSpec de teste"""
    data_dir = temp_directory / "snom_data"
    data_dir.mkdir()
    
    # Criar arquivo de texto simulando dados NeaSpec
    txt_file = data_dir / "snom_scan.txt"
    
    # Header simulado
    content = [
        "# www.neaspec.com",
        "# Project: Test Data",
        "# Description: Test SNOM scan",
        "# Date: 2025-01-21",
        "# Scan Area [µm]: 10.0 10.0 0.0",
        "# Pixel Area [px]: 10 10 50",
        "# Demodulation Mode: Fourier",
        "#",
        "Row\tColumn\tWavenumber\tO0A\tO0P\tO1A\tO1P"
    ]
    
    # Dados simulados
    for row in range(10):
        for col in range(10):
            for wn in np.linspace(800, 1800, 50):
                o0a = np.random.random()
                o0p = np.random.random()
                o1a = np.random.random()
                o1p = np.random.random()
                content.append(f"{row}\t{col}\t{wn:.2f}\t{o0a:.6f}\t{o0p:.6f}\t{o1a:.6f}\t{o1p:.6f}")
    
    txt_file.write_text('\n'.join(content))
    
    return data_dir


# ============================================================================
# FIXTURES - MOCKS E STUBS
# ============================================================================

@pytest.fixture
def mock_qt_application(monkeypatch):
    """Mock para QApplication para testes sem interface gráfica"""
    class MockQApplication:
        def __init__(self, *args, **kwargs):
            pass
        
        def exec(self):
            return 0
        
        def setApplicationName(self, name):
            pass
        
        def setApplicationVersion(self, version):
            pass
        
        def setOrganizationName(self, name):
            pass
        
        def setOrganizationDomain(self, domain):
            pass
    
    return MockQApplication


@pytest.fixture
def mock_file_dialog(monkeypatch):
    """Mock para QFileDialog"""
    class MockFileDialog:
        @staticmethod
        def getExistingDirectory(*args, **kwargs):
            return "/tmp/test_directory"
        
        @staticmethod
        def getSaveFileName(*args, **kwargs):
            return ("/tmp/test_file.csv", "CSV Files (*.csv)")
        
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return ("/tmp/test_file.nid", "Nanosurf (*.nid)")
    
    return MockFileDialog


# ============================================================================
# CONFIGURAÇÃO DE TESTES
# ============================================================================

def pytest_configure(config):
    """Configuração global de testes"""
    config.addinivalue_line(
        "markers", "unit: marca testes unitários"
    )
    config.addinivalue_line(
        "markers", "integration: marca testes de integração"
    )
    config.addinivalue_line(
        "markers", "slow: marca testes lentos"
    )
    config.addinivalue_line(
        "markers", "ui: marca testes de interface"
    )


# ============================================================================
# HELPERS
# ============================================================================

def assert_arrays_equal(arr1, arr2, rtol=1e-5, atol=1e-8):
    """Helper para comparar arrays numpy com tolerância"""
    np.testing.assert_allclose(arr1, arr2, rtol=rtol, atol=atol)


def assert_dataframes_equal(df1, df2):
    """Helper para comparar DataFrames pandas"""
    pd.testing.assert_frame_equal(df1, df2)


def create_test_spectral_data(n_points=100, n_spectra=25, dimensions=(5, 5)):
    """Factory para criar SpectralData de teste rapidamente"""
    V = np.linspace(-2.0, 2.0, n_points)
    I_base = 1e-9 * np.tanh(V / 0.5)
    
    data = {'V': V}
    for i in range(n_spectra):
        noise = np.random.normal(0, 1e-11, n_points)
        data[f'Spectrum_{i+1}'] = I_base + noise
    
    df = pd.DataFrame(data)
    
    metadata = SpectralMetadata(
        source_type='test',
        dimensions=dimensions,
        scan_mode='meander',
        units={'independent': 'V', 'dependent': 'A'}
    )
    
    return SpectralData(df, metadata)


def create_test_topography(height=50, width=50):
    """Factory para criar TopographyData de teste rapidamente"""
    data = np.random.random((height, width)) * 10  # 0-10 nm altura
    
    metadata = TopographyMetadata(
        dimensions=(height, width),
        physical_size=(1000.0, 1000.0),
        units='nm'
    )
    
    return TopographyData(data, metadata)
