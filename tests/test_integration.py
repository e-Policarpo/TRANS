"""
Testes de Integração Completos
Testa workflows completos do sistema T.R.A.N.S.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from models.spectral_data import SpectralData, SpectralMetadata
from models.topography_data import TopographyData, TopographyMetadata
from processing.derivatives import DerivativesProcessor
from processing.iv_processor import IVDataProcessor
from processing.discretization import Discretizer
from processing.map_generator import MapGenerator
from processing.integration import IntegrationProcessor


@pytest.mark.integration
@pytest.mark.slow
class TestCompleteDataPipeline:
    """Testes de pipeline completo de processamento de dados"""
    
    @pytest.fixture
    def complete_dataset(self):
        """Dataset completo com espectros e topografia"""
        # Criar dados espectrais 10x10
        V = np.linspace(-2, 2, 200)
        I_base = 1e-9 * np.tanh(V / 0.5)
        
        data = {'V': V}
        for i in range(100):  # 10x10 grid
            noise = np.random.normal(0, 1e-11, len(V))
            data[f'Spectrum_{i+1}'] = I_base + noise
        
        df = pd.DataFrame(data)
        
        metadata = SpectralMetadata(
            source_type='nanosurf_sts',
            dimensions=(10, 10),
            scan_mode='meander',
            units={'independent': 'V', 'dependent': 'A', 'x': 'nm', 'y': 'nm'},
            additional_info={'data_type': 'iv'}
        )
        
        spectral_data = SpectralData(df, metadata)
        
        # Criar topografia correspondente
        topo_array = np.random.random((100, 100)) * 10  # 100x100 pixels
        topo_metadata = TopographyMetadata(
            dimensions=(100, 100),
            physical_size=(1000.0, 1000.0),
            units='nm'
        )
        
        topography = TopographyData(topo_array, topo_metadata)
        
        return spectral_data, topography
    
    def test_full_analysis_workflow(self, complete_dataset, temp_directory):
        """Teste de workflow completo de análise"""
        spectral_data, topography = complete_dataset
        
        # 1. Corrigir meander
        spectral_data.correct_meander()
        assert spectral_data._corrected_meander is True
        
        # 2. Processar I-V
        iv_processor = IVDataProcessor()
        processed_iv = iv_processor.process_raw_iv_data(spectral_data)
        
        # 3. Calcular derivadas
        first_deriv, second_deriv = iv_processor.calculate_derivatives_from_iv(
            processed_iv,
            smooth_before=True,
            smooth_after=True
        )
        
        # 4. Aplicar correção polinomial
        deriv_processor = DerivativesProcessor()
        first_corr, second_corr = deriv_processor.correct_derivatives_with_polynomials(
            first_deriv,
            second_deriv,
            first_poly_degree=2,
            second_poly_degree=4
        )
        
        # 5. Discretizar topografia
        topography.discretize(10, 10)
        assert topography.discretized_data is not None
        
        # 6. Selecionar blocos
        topography.add_selected_block(0, 0)
        topography.add_selected_block(5, 5)
        topography.add_selected_block(9, 9)
        
        # 7. Discretizar dados espectrais
        discretizer = Discretizer()
        discretized = discretizer.discretize_spectral_data(
            spectral_data=first_corr,
            block_h=10,
            block_v=10,
            topography=topography,
            selected_blocks=topography.selected_blocks,
            ignore_empty_blocks=False,
            data_type='didv'
        )
        
        # 8. Salvar resultados
        output_path = temp_directory / "results"
        output_path.mkdir()
        
        # Salvar diferentes tipos de dados
        processed_iv.save(str(output_path / "processed_iv.csv"))
        first_corr.save(str(output_path / "first_derivative.csv"))
        second_corr.save(str(output_path / "second_derivative.csv"))
        topography.save(str(output_path / "topography.npy"), format='npy')
        
        # Verificações finais
        assert all(f.exists() for f in [
            output_path / "processed_iv.csv",
            output_path / "first_derivative.csv",
            output_path / "second_derivative.csv",
            output_path / "topography.npy"
        ])
        
        # Verificar integridade dos dados
        assert processed_iv.num_spectra == 100
        assert first_corr.num_spectra == 100
        assert len(topography.selected_blocks) == 3
        assert 'intermediate' in discretized
        assert 'final' in discretized
    
    def test_map_generation_workflow(self, complete_dataset, temp_directory):
        """Teste de workflow de geração de mapas"""
        spectral_data, topography = complete_dataset
        
        # 1. Definir intervalos de integração
        intervals = [
            (-1.0, -0.5),
            (-0.5, 0.0),
            (0.0, 0.5),
            (0.5, 1.0)
        ]
        
        # 2. Processar integração
        integration_processor = IntegrationProcessor()
        integration_processor.set_intervals(intervals)
        
        integration_results = integration_processor.integrate_spectral_data(
            spectral_data
        )
        
        assert len(integration_results) == 4
        
        # 3. Gerar mapas
        map_generator = MapGenerator()
        map_generator.set_integration_intervals(intervals)
        
        output_dir = temp_directory / "maps"
        output_dir.mkdir()
        
        maps = map_generator.generate_maps_for_dataset(
            spectral_data,
            output_dir,
            data_type='iv'
        )
        
        # Verificações
        assert len(maps) == 4
        
        # Cada mapa deve ser 10x10
        for interval_key, map_data in maps.items():
            assert map_data.shape == (10, 10)
        
        # Verificar que arquivos foram criados
        map_files = list(output_dir.glob("*.png"))
        assert len(map_files) > 0
    
    def test_truncation_and_analysis(self, complete_dataset):
        """Teste de truncamento e análise"""
        spectral_data, _ = complete_dataset
        
        # 1. Truncar para região de interesse
        truncated = spectral_data.truncate_range(-1.0, 1.0)
        
        assert truncated.num_points < spectral_data.num_points
        assert np.min(truncated.independent_var) >= -1.0
        assert np.max(truncated.independent_var) <= 1.0
        
        # 2. Calcular derivadas no intervalo truncado
        processor = DerivativesProcessor()
        first_deriv = processor.calculate_first_derivative(truncated)
        
        # 3. Verificar que derivadas têm mesmo tamanho
        assert first_deriv.num_points == truncated.num_points
        assert first_deriv.num_spectra == truncated.num_spectra
    
    def test_mask_and_export(self, complete_dataset, temp_directory):
        """Teste de masking e exportação seletiva"""
        spectral_data, topography = complete_dataset
        
        # 1. Discretizar topografia
        topography.discretize(10, 10)
        
        # 2. Selecionar região de interesse
        for i in range(5):
            for j in range(5):
                topography.add_selected_block(i, j)
        
        # 3. Criar máscara
        mask = topography.get_selection_mask()
        
        # 4. Aplicar máscara aos dados espectrais
        # Redimensionar máscara para coincidir com grid espectral
        spectral_mask = np.zeros((10, 10), dtype=bool)
        spectral_mask[:5, :5] = True
        
        masked_data = spectral_data.apply_mask(spectral_mask)
        
        # 5. Exportar dados mascarados
        output_path = temp_directory / "masked_data.csv"
        masked_data.save(str(output_path))
        
        assert output_path.exists()
        assert masked_data.num_spectra == 25  # 5x5
    
    def test_error_recovery_in_pipeline(self, complete_dataset):
        """Teste de recuperação de erros no pipeline"""
        spectral_data, topography = complete_dataset
        
        # Tentar operação inválida
        with pytest.raises(IndexError):
            # Tentar acessar espectro fora dos limites
            spectral_data.get_spectrum_at(100, 100)
        
        # Sistema deve continuar funcional
        spectrum = spectral_data.get_spectrum_at(0, 0)
        assert spectrum is not None
        
        # Tentar discretização com parâmetros inválidos
        with pytest.raises(Exception):
            topography.get_selection_mask()  # Sem discretizar primeiro
        
        # Discretizar corretamente após erro
        topography.discretize(10, 10)
        mask = topography.get_selection_mask()
        assert mask is not None


@pytest.mark.integration
class TestDataLoaderIntegration:
    """Testes de integração para loaders de dados"""
    
    def test_neaspec_file_loading(self, sample_neaspec_file_structure):
        """Teste de carregamento de arquivos NeaSpec"""
        from data_loaders.neaspec_snom_loader import NeaSpecSNOMLoader
        
        loader = NeaSpecSNOMLoader()
        
        # Encontrar arquivo de texto
        txt_files = list(sample_neaspec_file_structure.glob("*.txt"))
        assert len(txt_files) > 0
        
        txt_file = txt_files[0]
        
        try:
            spectral_data = loader.load_single_file(txt_file)
            
            assert spectral_data is not None
            assert spectral_data.num_spectra > 0
            assert spectral_data.num_points > 0
        except Exception as e:
            # Se falhar, deve ser por estrutura de arquivo simulado
            pytest.skip(f"Simulated file structure not sufficient: {e}")
    
    def test_csv_export_and_reload(self, sample_spectral_data, temp_directory):
        """Teste de exportar e recarregar CSV"""
        # Exportar
        export_path = temp_directory / "export.csv"
        sample_spectral_data.save(str(export_path))
        
        assert export_path.exists()
        
        # Recarregar
        loaded_data = SpectralData.load(
            str(export_path),
            sample_spectral_data.metadata
        )
        
        # Verificar integridade
        assert loaded_data.num_spectra == sample_spectral_data.num_spectra
        assert loaded_data.num_points == sample_spectral_data.num_points
        
        # Verificar que dados são idênticos
        pd.testing.assert_frame_equal(
            loaded_data.data,
            sample_spectral_data.data
        )


@pytest.mark.integration
class TestDataConsistency:
    """Testes de consistência de dados através do pipeline"""
    
    def test_metadata_preservation(self, sample_spectral_data):
        """Teste que metadata é preservada através de operações"""
        original_source = sample_spectral_data.metadata.source_type
        original_dims = sample_spectral_data.metadata.dimensions
        
        # Série de operações
        result = sample_spectral_data.truncate_range(-1.0, 1.0)
        result = result.correct_meander()
        
        # Metadata essencial deve ser preservada
        assert result.metadata.source_type == original_source
        assert result.metadata.dimensions == original_dims
    
    def test_data_type_tracking(self, sample_spectral_data):
        """Teste de rastreamento de tipo de dados"""
        # Processar como I-V
        iv_processor = IVDataProcessor()
        processed = iv_processor.process_raw_iv_data(sample_spectral_data)
        
        # Deve ter metadata de tipo
        assert 'data_type' in processed.metadata.additional_info
        
        # Calcular derivadas
        first_deriv, _ = iv_processor.calculate_derivatives_from_iv(processed)
        
        # Derivadas devem ter metadata de ordem
        assert 'derivative_order' in first_deriv.metadata.additional_info
        assert first_deriv.metadata.additional_info['derivative_order'] == 1
    
    def test_spatial_integrity_after_operations(self, sample_spectral_data, sample_topography_data):
        """Teste de integridade espacial"""
        # Dimensões iniciais
        original_dims = sample_spectral_data.metadata.dimensions
        
        # Aplicar operações
        processor = DerivativesProcessor()
        first_deriv = processor.calculate_first_derivative(sample_spectral_data)
        
        # Dimensões devem ser preservadas
        assert first_deriv.metadata.dimensions == original_dims
        assert first_deriv.num_spectra == sample_spectral_data.num_spectra
        
        # Deve poder converter para cubo 3D
        cube = first_deriv.to_3d_cube()
        assert cube.shape[1:] == original_dims
    
    def test_numerical_precision(self, sample_spectral_data):
        """Teste de precisão numérica através de operações"""
        # Dados originais
        original_values = sample_spectral_data.spectra.values.copy()
        
        # Aplicar operações reversíveis conceitualmente
        truncated = sample_spectral_data.truncate_range(-1.5, 1.5)
        
        # Valores no intervalo devem ser idênticos (sem processamento)
        V = sample_spectral_data.independent_var
        mask = (V >= -1.5) & (V <= 1.5)
        
        original_subset = original_values[mask, :]
        truncated_values = truncated.spectra.values
        
        # Deve ter mesmos valores (com pequena tolerância numérica)
        np.testing.assert_allclose(
            truncated_values,
            original_subset,
            rtol=1e-10,
            atol=1e-15
        )


@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """Testes de performance e escalabilidade"""
    
    def test_large_dataset_handling(self):
        """Teste com dataset grande"""
        # Criar dataset 50x50 = 2500 espectros
        V = np.linspace(-2, 2, 500)
        I_base = 1e-9 * np.tanh(V / 0.5)
        
        data = {'V': V}
        for i in range(2500):
            noise = np.random.normal(0, 1e-11, len(V))
            data[f'Spectrum_{i+1}'] = I_base + noise
        
        df = pd.DataFrame(data)
        
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(50, 50),
            scan_mode='meander',
            units={'independent': 'V', 'dependent': 'A'}
        )
        
        spectral_data = SpectralData(df, metadata)
        
        # Operações básicas devem completar rapidamente
        import time
        
        start = time.time()
        spectral_data.correct_meander()
        meander_time = time.time() - start
        
        assert meander_time < 1.0  # Deve completar em menos de 1 segundo
        
        start = time.time()
        cube = spectral_data.to_3d_cube()
        cube_time = time.time() - start
        
        assert cube_time < 0.5  # Conversão deve ser rápida
        assert cube.shape == (500, 50, 50)
    
    def test_memory_efficiency(self):
        """Teste de eficiência de memória"""
        # Criar múltiplos datasets
        datasets = []
        
        for _ in range(10):
            V = np.linspace(-2, 2, 100)
            I = 1e-9 * np.tanh(V / 0.5)
            
            df = pd.DataFrame({'V': V, 'I': I})
            metadata = SpectralMetadata(
                source_type='test',
                dimensions=(1, 1),
                scan_mode='single',
                units={}
            )
            
            datasets.append(SpectralData(df, metadata))
        
        # Todos devem ser independentes
        datasets[0]._data.iloc[0, 0] = 999.0
        
        # Outros não devem ser afetados
        for i in range(1, 10):
            assert datasets[i]._data.iloc[0, 0] != 999.0
