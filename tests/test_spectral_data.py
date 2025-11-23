"""
Testes Unitários para SpectralData
Testa a classe principal de dados espectrais
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from models.spectral_data import SpectralData, SpectralMetadata


class TestSpectralMetadata:
    """Testes para SpectralMetadata"""
    
    def test_create_metadata(self):
        """Teste de criação básica de metadata"""
        metadata = SpectralMetadata(
            source_type='nanosurf_sts',
            dimensions=(10, 10),
            scan_mode='meander',
            units={'independent': 'V', 'dependent': 'A'}
        )
        
        assert metadata.source_type == 'nanosurf_sts'
        assert metadata.dimensions == (10, 10)
        assert metadata.scan_mode == 'meander'
        assert metadata.units['independent'] == 'V'
    
    def test_metadata_with_additional_info(self):
        """Teste de metadata com informações adicionais"""
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(5, 5),
            scan_mode='raster',
            units={},
            additional_info={'custom_field': 'custom_value'}
        )
        
        assert metadata.additional_info['custom_field'] == 'custom_value'
    
    def test_metadata_defaults(self):
        """Teste de valores padrão"""
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(1, 1),
            scan_mode='single',
            units={}
        )
        
        assert metadata.acquisition_date is None
        assert metadata.additional_info == {}


class TestSpectralData:
    """Testes para SpectralData"""
    
    def test_create_spectral_data(self, sample_spectral_dataframe, sample_spectral_metadata):
        """Teste de criação de SpectralData"""
        spectral_data = SpectralData(sample_spectral_dataframe, sample_spectral_metadata)
        
        assert spectral_data is not None
        assert spectral_data.num_spectra == 25
        assert spectral_data.num_points == 100
    
    def test_independent_var_property(self, sample_spectral_data):
        """Teste da propriedade independent_var"""
        V = sample_spectral_data.independent_var
        
        assert isinstance(V, np.ndarray)
        assert len(V) == 100
        assert V[0] == pytest.approx(-2.0, rel=1e-2)
        assert V[-1] == pytest.approx(2.0, rel=1e-2)
    
    def test_independent_var_name_property(self, sample_spectral_data):
        """Teste da propriedade independent_var_name"""
        name = sample_spectral_data.independent_var_name
        assert name == 'V'
    
    def test_spectra_property(self, sample_spectral_data):
        """Teste da propriedade spectra"""
        spectra = sample_spectral_data.spectra
        
        assert isinstance(spectra, pd.DataFrame)
        assert len(spectra.columns) == 25
        assert len(spectra) == 100
    
    def test_num_spectra_property(self, sample_spectral_data):
        """Teste da propriedade num_spectra"""
        assert sample_spectral_data.num_spectra == 25
    
    def test_num_points_property(self, sample_spectral_data):
        """Teste da propriedade num_points"""
        assert sample_spectral_data.num_points == 100
    
    def test_validate_data_valid(self, sample_spectral_dataframe):
        """Teste de validação com dados válidos"""
        # Não deve lançar exceção
        SpectralData.validate_data(sample_spectral_dataframe)
    
    def test_validate_data_invalid_type(self):
        """Teste de validação com tipo inválido"""
        with pytest.raises(TypeError, match="Data must be a pandas DataFrame"):
            SpectralData.validate_data("not a dataframe")
    
    def test_validate_data_too_few_columns(self):
        """Teste de validação com poucas colunas"""
        df = pd.DataFrame({'V': [1, 2, 3]})
        
        with pytest.raises(ValueError, match="at least 2 columns"):
            SpectralData.validate_data(df)
    
    def test_validate_data_non_numeric_first_column(self):
        """Teste de validação com primeira coluna não numérica"""
        df = pd.DataFrame({
            'V': ['a', 'b', 'c'],
            'I': [1, 2, 3]
        })
        
        with pytest.raises(ValueError, match="First column must be numeric"):
            SpectralData.validate_data(df)
    
    def test_correct_meander_basic(self, sample_spectral_data):
        """Teste de correção de meander básica"""
        # Aplicar correção
        result = sample_spectral_data.correct_meander()
        
        # Deve retornar self
        assert result is sample_spectral_data
        assert sample_spectral_data._corrected_meander is True
    
    def test_correct_meander_already_corrected(self, sample_spectral_data):
        """Teste de correção quando já corrigido"""
        sample_spectral_data.correct_meander()
        
        # Segunda chamada não deve fazer nada
        sample_spectral_data.correct_meander()
        
        assert sample_spectral_data._corrected_meander is True
    
    def test_correct_meander_force(self, sample_spectral_data):
        """Teste de correção forçada"""
        sample_spectral_data.correct_meander()
        
        # Forçar nova correção
        result = sample_spectral_data.correct_meander(force=True)
        
        assert result is sample_spectral_data
    
    def test_correct_meander_wrong_scan_mode(self, sample_spectral_dataframe):
        """Teste de correção com scan mode incorreto"""
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(5, 5),
            scan_mode='raster',  # Não meander
            units={}
        )
        
        spectral_data = SpectralData(sample_spectral_dataframe, metadata)
        result = spectral_data.correct_meander()
        
        # Não deve aplicar correção
        assert result._corrected_meander is False
    
    def test_to_3d_cube(self, sample_spectral_data):
        """Teste de conversão para cubo 3D"""
        cube = sample_spectral_data.to_3d_cube()
        
        assert cube.shape == (100, 5, 5)  # (n_points, dim_v, dim_h)
        assert isinstance(cube, np.ndarray)
    
    def test_to_3d_cube_wrong_dimensions(self, sample_spectral_dataframe):
        """Teste de cubo 3D com dimensões incorretas"""
        metadata = SpectralMetadata(
            source_type='test',
            dimensions=(10, 10),  # Errado: deveria ser 5x5
            scan_mode='meander',
            units={}
        )
        
        spectral_data = SpectralData(sample_spectral_dataframe, metadata)
        
        with pytest.raises(ValueError, match="Cannot reshape"):
            spectral_data.to_3d_cube()
    
    def test_apply_mask(self, sample_spectral_data):
        """Teste de aplicação de máscara"""
        # Criar máscara 5x5 (metade selecionada)
        mask = np.zeros((5, 5), dtype=bool)
        mask[:, :3] = True  # Selecionar primeiras 3 colunas
        
        masked_data = sample_spectral_data.apply_mask(mask)
        
        assert masked_data.num_spectra == 15  # 5 * 3
        assert isinstance(masked_data, SpectralData)
    
    def test_apply_mask_wrong_shape(self, sample_spectral_data):
        """Teste de máscara com forma incorreta"""
        mask = np.ones((10, 10), dtype=bool)  # Forma errada
        
        with pytest.raises(ValueError, match="doesn't match"):
            sample_spectral_data.apply_mask(mask)
    
    def test_get_spectrum_at(self, sample_spectral_data):
        """Teste de obtenção de espectro em posição específica"""
        spectrum = sample_spectral_data.get_spectrum_at(2, 3)
        
        assert isinstance(spectrum, pd.Series)
        assert len(spectrum) == 100
        assert spectrum.name == "Spectrum_r2_c3"
    
    def test_get_spectrum_at_out_of_bounds(self, sample_spectral_data):
        """Teste de espectro fora dos limites"""
        with pytest.raises(IndexError, match="out of bounds"):
            sample_spectral_data.get_spectrum_at(10, 10)
    
    def test_truncate_range(self, sample_spectral_data):
        """Teste de truncamento de intervalo"""
        truncated = sample_spectral_data.truncate_range(-1.0, 1.0)
        
        assert isinstance(truncated, SpectralData)
        assert truncated.num_points < 100  # Deve ter menos pontos
        assert np.min(truncated.independent_var) >= -1.0
        assert np.max(truncated.independent_var) <= 1.0
    
    def test_truncate_range_invalid(self, sample_spectral_data):
        """Teste de truncamento com intervalo inválido"""
        # Min >= Max
        truncated = sample_spectral_data.truncate_range(1.0, -1.0)
        
        # Deve retornar dados vazios ou muito pequenos
        assert truncated.num_points < sample_spectral_data.num_points
    
    def test_save_and_load(self, sample_spectral_data, temp_directory):
        """Teste de salvar e carregar"""
        filepath = temp_directory / "test_spectral.csv"
        
        # Salvar
        sample_spectral_data.save(str(filepath))
        assert filepath.exists()
        
        # Carregar
        loaded_data = SpectralData.load(
            str(filepath),
            sample_spectral_data.metadata
        )
        
        assert loaded_data.num_spectra == sample_spectral_data.num_spectra
        assert loaded_data.num_points == sample_spectral_data.num_points
    
    def test_copy(self, sample_spectral_data):
        """Teste de cópia profunda"""
        copied = sample_spectral_data.copy()
        
        assert copied is not sample_spectral_data
        assert copied.num_spectra == sample_spectral_data.num_spectra
        
        # Modificar cópia não deve afetar original
        copied._data.iloc[0, 0] = 999.0
        assert sample_spectral_data._data.iloc[0, 0] != 999.0
    
    def test_repr(self, sample_spectral_data):
        """Teste de representação string"""
        repr_str = repr(sample_spectral_data)
        
        assert "SpectralData" in repr_str
        assert "test" in repr_str
        assert "5, 5" in repr_str


@pytest.mark.integration
class TestSpectralDataIntegration:
    """Testes de integração para SpectralData"""
    
    def test_full_workflow(self, sample_spectral_data):
        """Teste de workflow completo"""
        # 1. Corrigir meander
        sample_spectral_data.correct_meander()
        
        # 2. Truncar
        truncated = sample_spectral_data.truncate_range(-1.5, 1.5)
        
        # 3. Aplicar máscara
        mask = np.ones(sample_spectral_data.metadata.dimensions, dtype=bool)
        mask[0, 0] = False  # Excluir um ponto
        
        masked = truncated.apply_mask(mask)
        
        # 4. Converter para cubo
        cube = masked.to_3d_cube()
        
        # Verificações
        assert masked.num_spectra == 24  # 25 - 1
        assert cube.shape[1:] == (5, 5)
    
    def test_multiple_operations_preserve_metadata(self, sample_spectral_data):
        """Teste que operações preservam metadata importante"""
        original_source = sample_spectral_data.metadata.source_type
        
        # Aplicar várias operações
        result = sample_spectral_data.truncate_range(-1.0, 1.0)
        result = result.correct_meander()
        
        # Metadata base deve ser preservado
        assert result.metadata.source_type == original_source
