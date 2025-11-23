"""
Testes para Processadores de Dados
Testa DerivativesProcessor e IVDataProcessor
"""

import pytest
import numpy as np
import pandas as pd

from processing.derivatives import DerivativesProcessor
from processing.iv_processor import IVDataProcessor
from models.spectral_data import SpectralData, SpectralMetadata


class TestDerivativesProcessor:
    """Testes para DerivativesProcessor"""
    
    @pytest.fixture
    def processor(self):
        """Fixture para processor"""
        return DerivativesProcessor(smooth_window=11, smooth_polyorder=3)
    
    @pytest.fixture
    def test_data_for_derivatives(self):
        """Dados de teste para derivadas"""
        # Criar dados com função conhecida: y = x^3
        V = np.linspace(-2, 2, 100)
        I_base = V ** 3
        
        data = {'V': V}
        for i in range(5):
            noise = np.random.normal(0, 0.01, len(V))
            data[f'Spectrum_{i+1}'] = I_base + noise
        
        df = pd.DataFrame(data)
        
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(5, 1),
            scan_mode='single',
            units={'independent': 'V', 'dependent': 'A'}
        )
        
        return SpectralData(df, metadata)
    
    def test_create_processor(self, processor):
        """Teste de criação do processor"""
        assert processor.smooth_window == 11
        assert processor.smooth_polyorder == 3
    
    def test_calculate_first_derivative(self, processor, test_data_for_derivatives):
        """Teste de cálculo de primeira derivada"""
        first_deriv = processor.calculate_first_derivative(
            test_data_for_derivatives,
            smooth_before=True,
            smooth_after=True
        )
        
        assert isinstance(first_deriv, SpectralData)
        assert first_deriv.num_points == test_data_for_derivatives.num_points
        assert first_deriv.num_spectra == test_data_for_derivatives.num_spectra
        
        # Para y = x^3, dy/dx = 3x^2
        V = first_deriv.independent_var
        expected_deriv = 3 * V ** 2
        
        # Verificar que a derivada calculada está próxima da esperada
        actual_deriv = first_deriv.spectra.iloc[:, 0].values
        
        # Com smoothing, não será exata mas deve estar próxima
        correlation = np.corrcoef(expected_deriv, actual_deriv)[0, 1]
        assert correlation > 0.95  # Alta correlação
    
    def test_calculate_first_derivative_no_smoothing(self, processor, test_data_for_derivatives):
        """Teste sem smoothing"""
        first_deriv = processor.calculate_first_derivative(
            test_data_for_derivatives,
            smooth_before=False,
            smooth_after=False
        )
        
        assert isinstance(first_deriv, SpectralData)
        
        # Sem smoothing, pode ter mais ruído mas ainda deve funcionar
        assert first_deriv.num_points == test_data_for_derivatives.num_points
    
    def test_calculate_second_derivative(self, processor, test_data_for_derivatives):
        """Teste de cálculo de segunda derivada"""
        second_deriv = processor.calculate_second_derivative(
            test_data_for_derivatives,
            smooth_before=True,
            smooth_after=True
        )
        
        assert isinstance(second_deriv, SpectralData)
        assert second_deriv.num_points == test_data_for_derivatives.num_points
        
        # Para y = x^3, d²y/dx² = 6x
        V = second_deriv.independent_var
        expected_second_deriv = 6 * V
        
        actual_second_deriv = second_deriv.spectra.iloc[:, 0].values
        
        # Verificar correlação
        correlation = np.corrcoef(expected_second_deriv, actual_second_deriv)[0, 1]
        assert correlation > 0.9
    
    def test_calculate_second_derivative_from_first(self, processor, test_data_for_derivatives):
        """Teste de segunda derivada a partir da primeira"""
        # Calcular primeira derivada
        first_deriv = processor.calculate_first_derivative(test_data_for_derivatives)
        
        # Calcular segunda a partir da primeira
        second_deriv = processor.calculate_second_derivative(
            test_data_for_derivatives,
            from_first=first_deriv
        )
        
        assert isinstance(second_deriv, SpectralData)
    
    def test_polynomial_baseline_correction(self, processor, test_data_for_derivatives):
        """Teste de correção de baseline polinomial"""
        corrected = processor.polynomial_baseline_correction(
            test_data_for_derivatives,
            poly_degree=2
        )
        
        assert isinstance(corrected, SpectralData)
        assert corrected.num_points == test_data_for_derivatives.num_points
        
        # Após correção, baseline deve estar mais próximo de zero
        mean_value = np.mean(corrected.spectra.values)
        assert abs(mean_value) < abs(np.mean(test_data_for_derivatives.spectra.values))
    
    def test_correct_derivatives_with_polynomials(self, processor, test_data_for_derivatives):
        """Teste de correção de derivadas com polinômios"""
        # Calcular derivadas
        first = processor.calculate_first_derivative(test_data_for_derivatives)
        second = processor.calculate_second_derivative(test_data_for_derivatives)
        
        # Corrigir
        first_corr, second_corr = processor.correct_derivatives_with_polynomials(
            first, second,
            first_poly_degree=2,
            second_poly_degree=4
        )
        
        assert isinstance(first_corr, SpectralData)
        assert isinstance(second_corr, SpectralData)
        
        # Derivadas corrigidas devem ter metadata atualizada
        assert 'baseline_corrected' in first_corr.metadata.additional_info
        assert first_corr.metadata.additional_info['baseline_corrected'] is True
    
    def test_calculate_derivatives_batch(self, processor, test_data_for_derivatives):
        """Teste de cálculo em lote"""
        results = processor.calculate_derivatives_batch(
            test_data_for_derivatives,
            calculate_second=True,
            apply_correction=True
        )
        
        assert 'first' in results
        assert 'second' in results
        assert 'first_corrected' in results
        assert 'second_corrected' in results
        
        # Todas devem ser SpectralData
        for key, value in results.items():
            assert isinstance(value, SpectralData)
    
    def test_smooth_data_internal(self, processor):
        """Teste de método interno de smoothing"""
        # Dados com ruído
        data = np.random.random((100, 5))
        
        smoothed = processor._smooth_data(data)
        
        assert smoothed.shape == data.shape
        
        # Dados suavizados devem ter menos variação
        assert np.std(smoothed) < np.std(data)
    
    def test_smooth_data_short_array(self, processor):
        """Teste de smoothing com array curto"""
        # Array menor que janela
        data = np.random.random((5, 3))
        
        # Não deve lançar erro
        smoothed = processor._smooth_data(data)
        
        assert smoothed.shape == data.shape


class TestIVDataProcessor:
    """Testes para IVDataProcessor"""
    
    @pytest.fixture
    def processor(self):
        """Fixture para IV processor"""
        return IVDataProcessor(smooth_window=11, smooth_polyorder=3)
    
    @pytest.fixture
    def iv_data(self):
        """Dados I-V de teste"""
        V = np.linspace(-2, 2, 100)
        # I-V típico: comportamento não-linear
        I_base = 1e-9 * np.tanh(V / 0.5)
        
        data = {'V': V}
        for i in range(5):
            noise = np.random.normal(0, 1e-11, len(V))
            data[f'I_{i+1}'] = I_base + noise
        
        df = pd.DataFrame(data)
        
        metadata = SpectralMetadata(
            source_type='nanosurf_sts',
            dimensions=(5, 1),
            scan_mode='single',
            units={'independent': 'V', 'dependent': 'A'},
            additional_info={'data_type': 'iv'}
        )
        
        return SpectralData(df, metadata)
    
    def test_create_processor(self, processor):
        """Teste de criação do processor"""
        assert processor.smooth_window == 11
        assert processor.smooth_polyorder == 3
    
    def test_process_raw_iv_data(self, processor, iv_data):
        """Teste de processamento de dados I-V brutos"""
        processed = processor.process_raw_iv_data(iv_data)
        
        assert isinstance(processed, SpectralData)
        assert processed.num_points == iv_data.num_points
        assert processed.num_spectra == iv_data.num_spectra
        
        # Metadata deve indicar processamento
        assert processed.metadata.additional_info.get('smoothed') is True
        assert 'data_type' in processed.metadata.additional_info
    
    def test_calculate_derivatives_from_iv(self, processor, iv_data):
        """Teste de cálculo de derivadas a partir de I-V"""
        first_deriv, second_deriv = processor.calculate_derivatives_from_iv(
            iv_data,
            smooth_before=True,
            smooth_after=True
        )
        
        assert isinstance(first_deriv, SpectralData)
        assert isinstance(second_deriv, SpectralData)
        
        # Primeira derivada é condutância (dI/dV)
        assert first_deriv.num_points == iv_data.num_points
        
        # Unidades devem ser atualizadas
        assert 'A/V' in first_deriv.metadata.units.get('dependent', '')
    
    def test_calculate_derivatives_units(self, processor, iv_data):
        """Teste de atualização de unidades"""
        first_deriv, second_deriv = processor.calculate_derivatives_from_iv(iv_data)
        
        # Primeira derivada: A/V
        first_unit = first_deriv.metadata.units['dependent']
        assert 'A/V' in first_unit
        
        # Segunda derivada: A/V²
        second_unit = second_deriv.metadata.units['dependent']
        assert 'A/V²' in second_unit or 'A/V2' in second_unit
    
    def test_smooth_data_configuration(self, processor, iv_data):
        """Teste de configuração de smoothing"""
        # Alterar parâmetros
        processor.smooth_window = 21
        processor.smooth_polyorder = 5
        
        processed = processor.process_raw_iv_data(iv_data)
        
        # Deve usar novos parâmetros
        assert processed.metadata.additional_info['smooth_window'] == 21
        assert processed.metadata.additional_info['smooth_polyorder'] == 5


@pytest.mark.integration
class TestProcessorsIntegration:
    """Testes de integração entre processadores"""
    
    def test_iv_to_derivatives_full_pipeline(self):
        """Teste de pipeline completo: I-V -> derivadas"""
        # 1. Criar dados I-V
        V = np.linspace(-2, 2, 200)
        I = 1e-9 * np.tanh(V / 0.5)
        
        df = pd.DataFrame({'V': V, 'I': I})
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(1, 1),
            scan_mode='single',
            units={'independent': 'V', 'dependent': 'A'}
        )
        
        iv_data = SpectralData(df, metadata)
        
        # 2. Processar I-V
        iv_processor = IVDataProcessor()
        processed_iv = iv_processor.process_raw_iv_data(iv_data)
        
        # 3. Calcular derivadas
        first_deriv, second_deriv = iv_processor.calculate_derivatives_from_iv(
            processed_iv
        )
        
        # 4. Aplicar correção polinomial
        deriv_processor = DerivativesProcessor()
        first_corr, second_corr = deriv_processor.correct_derivatives_with_polynomials(
            first_deriv,
            second_deriv
        )
        
        # Verificações
        assert isinstance(processed_iv, SpectralData)
        assert isinstance(first_deriv, SpectralData)
        assert isinstance(second_deriv, SpectralData)
        assert isinstance(first_corr, SpectralData)
        assert isinstance(second_corr, SpectralData)
        
        # Todos devem ter mesmo número de pontos
        assert (processed_iv.num_points == first_deriv.num_points == 
                second_deriv.num_points == first_corr.num_points == 
                second_corr.num_points)
    
    def test_derivatives_preserve_spatial_structure(self, sample_spectral_data):
        """Teste que derivadas preservam estrutura espacial"""
        processor = DerivativesProcessor()
        
        # Calcular derivadas
        first_deriv = processor.calculate_first_derivative(sample_spectral_data)
        
        # Dimensões devem ser preservadas
        assert first_deriv.metadata.dimensions == sample_spectral_data.metadata.dimensions
        assert first_deriv.num_spectra == sample_spectral_data.num_spectra
        
        # Deve poder aplicar meander correction
        first_deriv.correct_meander()
        assert first_deriv._corrected_meander is True
    
    def test_multiple_smoothing_iterations(self):
        """Teste de múltiplas iterações de smoothing"""
        # Dados com muito ruído
        V = np.linspace(-1, 1, 50)
        I = np.sin(2 * np.pi * V) + np.random.normal(0, 0.5, len(V))
        
        df = pd.DataFrame({'V': V, 'I': I})
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(1, 1),
            scan_mode='single',
            units={}
        )
        
        data = SpectralData(df, metadata)
        
        # Processar múltiplas vezes
        processor = IVDataProcessor(smooth_window=5, smooth_polyorder=2)
        
        processed1 = processor.process_raw_iv_data(data)
        processed2 = processor.process_raw_iv_data(processed1)
        
        # Segunda iteração deve suavizar ainda mais
        std1 = np.std(processed1.spectra.values)
        std2 = np.std(processed2.spectra.values)
        
        assert std2 <= std1  # Mais suave ou igual
