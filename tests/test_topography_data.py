"""
Testes Unitários para TopographyData
Testa a classe de dados topográficos
"""

import pytest
import numpy as np
from pathlib import Path
from PIL import Image

from models.topography_data import TopographyData, TopographyMetadata


class TestTopographyMetadata:
    """Testes para TopographyMetadata"""
    
    def test_create_metadata(self):
        """Teste de criação básica"""
        metadata = TopographyMetadata(
            dimensions=(100, 100),
            physical_size=(1000.0, 1000.0),
            units='nm',
            scan_mode='raster'
        )
        
        assert metadata.dimensions == (100, 100)
        assert metadata.physical_size == (1000.0, 1000.0)
        assert metadata.units == 'nm'
    
    def test_pixel_size_property(self):
        """Teste de cálculo de tamanho de pixel"""
        metadata = TopographyMetadata(
            dimensions=(100, 100),
            physical_size=(1000.0, 1000.0),
            units='nm'
        )
        
        pixel_size = metadata.pixel_size
        assert pixel_size == (10.0, 10.0)  # 1000/100 = 10 nm/pixel
    
    def test_pixel_size_no_physical_size(self):
        """Teste quando não há tamanho físico"""
        metadata = TopographyMetadata(
            dimensions=(100, 100),
            units='nm'
        )
        
        assert metadata.pixel_size is None


class TestTopographyData:
    """Testes para TopographyData"""
    
    def test_create_topography(self, sample_topography_array, sample_topography_metadata):
        """Teste de criação básica"""
        topo = TopographyData(sample_topography_array, sample_topography_metadata)
        
        assert topo.shape == (50, 50)
        assert topo.height == 50
        assert topo.width == 50
    
    def test_create_with_invalid_dimensions(self):
        """Teste com dimensões inválidas"""
        data = np.random.random((10, 10, 10))  # 3D não permitido
        
        with pytest.raises(ValueError, match="must be 2D"):
            TopographyData(data)
    
    def test_shape_property(self, sample_topography_data):
        """Teste da propriedade shape"""
        assert sample_topography_data.shape == (50, 50)
    
    def test_height_width_properties(self, sample_topography_data):
        """Teste das propriedades height e width"""
        assert sample_topography_data.height == 50
        assert sample_topography_data.width == 50
    
    def test_normalize_default(self, sample_topography_data):
        """Teste de normalização padrão"""
        normalized = sample_topography_data.normalize()
        
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
        assert normalized.shape == sample_topography_data.shape
    
    def test_normalize_with_bounds(self, sample_topography_data):
        """Teste de normalização com limites personalizados"""
        normalized = sample_topography_data.normalize(vmin=-5.0, vmax=15.0)
        
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
    
    def test_normalize_equal_vmin_vmax(self):
        """Teste de normalização com vmin == vmax"""
        data = np.ones((10, 10)) * 5.0  # Todos valores iguais
        topo = TopographyData(data)
        
        normalized = topo.normalize()
        
        # Deve retornar zeros quando vmin == vmax
        assert np.all(normalized == 0.0)
    
    def test_to_image_grayscale(self, sample_topography_data):
        """Teste de conversão para imagem grayscale"""
        image = sample_topography_data.to_image(colormap='gray')
        
        assert isinstance(image, Image.Image)
        assert image.mode == 'L'  # Grayscale
        assert image.size == (50, 50)
    
    def test_to_image_colormap(self, sample_topography_data):
        """Teste de conversão para imagem colorida"""
        image = sample_topography_data.to_image(colormap='viridis')
        
        assert isinstance(image, Image.Image)
        assert image.mode == 'RGB'
        assert image.size == (50, 50)
    
    def test_discretize_exact_fit(self, sample_topography_data):
        """Teste de discretização com tamanho exato"""
        # 50x50 com blocos 10x10 = 5x5 blocos exatos
        result = sample_topography_data.discretize(10, 10, resize_to_fit=False)
        
        assert result is sample_topography_data  # Retorna self
        assert sample_topography_data.discretized_data is not None
        assert sample_topography_data.discretized_data.shape == (5, 5)
        assert sample_topography_data.block_size == (10, 10)
    
    def test_discretize_with_resize(self):
        """Teste de discretização com redimensionamento"""
        # Criar topografia que não se encaixa perfeitamente
        data = np.random.random((47, 53))
        topo = TopographyData(data)
        
        topo.discretize(10, 10, resize_to_fit=True)
        
        # Deve ter sido redimensionado
        assert topo.height == 40  # 47 -> 40 (4*10)
        assert topo.width == 50   # 53 -> 50 (5*10)
        assert topo.discretized_data.shape == (4, 5)
    
    def test_discretize_without_resize(self):
        """Teste de discretização sem redimensionamento"""
        data = np.random.random((47, 53))
        topo = TopographyData(data)
        
        topo.discretize(10, 10, resize_to_fit=False)
        
        # Dados originais não devem mudar
        assert topo.height == 47
        assert topo.width == 53
        # Blocos serão cortados
        assert topo.discretized_data.shape == (4, 5)
    
    def test_add_selected_block(self, sample_topography_data):
        """Teste de adicionar bloco selecionado"""
        sample_topography_data.discretize(10, 10)
        
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(1, 1)
        
        assert len(sample_topography_data.selected_blocks) == 2
        assert (0, 0) in sample_topography_data.selected_blocks
        assert (1, 1) in sample_topography_data.selected_blocks
    
    def test_add_duplicate_block(self, sample_topography_data):
        """Teste de adicionar bloco duplicado"""
        sample_topography_data.discretize(10, 10)
        
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(0, 0)  # Duplicado
        
        # Não deve duplicar
        assert len(sample_topography_data.selected_blocks) == 1
    
    def test_remove_selected_block(self, sample_topography_data):
        """Teste de remover bloco selecionado"""
        sample_topography_data.discretize(10, 10)
        
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(1, 1)
        
        sample_topography_data.remove_selected_block(0, 0)
        
        assert len(sample_topography_data.selected_blocks) == 1
        assert (0, 0) not in sample_topography_data.selected_blocks
    
    def test_toggle_block_selection(self, sample_topography_data):
        """Teste de alternância de seleção"""
        sample_topography_data.discretize(10, 10)
        
        # Adicionar
        sample_topography_data.toggle_block_selection(0, 0)
        assert (0, 0) in sample_topography_data.selected_blocks
        
        # Remover
        sample_topography_data.toggle_block_selection(0, 0)
        assert (0, 0) not in sample_topography_data.selected_blocks
    
    def test_clear_selection(self, sample_topography_data):
        """Teste de limpar seleção"""
        sample_topography_data.discretize(10, 10)
        
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(1, 1)
        sample_topography_data.add_selected_block(2, 2)
        
        sample_topography_data.clear_selection()
        
        assert len(sample_topography_data.selected_blocks) == 0
    
    def test_get_selection_mask(self, sample_topography_data):
        """Teste de obter máscara de seleção"""
        sample_topography_data.discretize(10, 10)
        
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(1, 1)
        
        mask = sample_topography_data.get_selection_mask()
        
        assert mask.shape == (50, 50)
        assert mask.dtype == bool
        
        # Verificar blocos selecionados
        assert np.all(mask[0:10, 0:10] == True)    # Bloco (0,0)
        assert np.all(mask[10:20, 10:20] == True)  # Bloco (1,1)
        assert np.all(mask[20:30, 20:30] == False) # Bloco (2,2) não selecionado
    
    def test_get_selection_mask_not_discretized(self, sample_topography_data):
        """Teste de máscara sem discretização"""
        with pytest.raises(ValueError, match="not discretized"):
            sample_topography_data.get_selection_mask()
    
    def test_get_block_value(self, sample_topography_data):
        """Teste de obter valor de bloco"""
        sample_topography_data.discretize(10, 10)
        
        value = sample_topography_data.get_block_value(0, 0)
        
        assert isinstance(value, (int, float, np.number))
    
    def test_get_block_value_out_of_bounds(self, sample_topography_data):
        """Teste de valor de bloco fora dos limites"""
        sample_topography_data.discretize(10, 10)
        
        with pytest.raises(IndexError, match="out of bounds"):
            sample_topography_data.get_block_value(10, 10)
    
    def test_save_and_load_tiff(self, sample_topography_data, temp_directory):
        """Teste de salvar e carregar TIFF"""
        filepath = temp_directory / "topo.tiff"
        
        sample_topography_data.save(str(filepath), format='tiff')
        assert filepath.exists()
        
        loaded = TopographyData.load(str(filepath))
        assert loaded.shape == sample_topography_data.shape
    
    def test_save_and_load_png(self, sample_topography_data, temp_directory):
        """Teste de salvar e carregar PNG"""
        filepath = temp_directory / "topo.png"
        
        sample_topography_data.save(str(filepath), format='png')
        assert filepath.exists()
        
        loaded = TopographyData.load(str(filepath))
        assert loaded.shape == sample_topography_data.shape
    
    def test_save_and_load_npy(self, sample_topography_data, temp_directory):
        """Teste de salvar e carregar NPY"""
        filepath = temp_directory / "topo.npy"
        
        sample_topography_data.save(str(filepath), format='npy')
        assert filepath.exists()
        
        loaded = TopographyData.load(str(filepath))
        assert loaded.shape == sample_topography_data.shape
        
        # NPY preserva valores exatos
        np.testing.assert_array_equal(loaded.data, sample_topography_data.data)
    
    def test_save_unsupported_format(self, sample_topography_data, temp_directory):
        """Teste de formato não suportado"""
        filepath = temp_directory / "topo.xyz"
        
        with pytest.raises(ValueError, match="Unsupported format"):
            sample_topography_data.save(str(filepath), format='xyz')
    
    def test_from_forward_backward(self):
        """Teste de criação a partir de scans forward/backward"""
        forward = np.random.random((50, 50))
        backward = np.random.random((50, 50))
        
        topo = TopographyData.from_forward_backward(forward, backward, flip_vertical=True)
        
        assert topo.shape == (50, 50)
        # Deve ser a média
        expected = (forward + backward) / 2
        expected = np.flipud(expected)  # Invertido verticalmente
        
        np.testing.assert_array_equal(topo.data, expected)
    
    def test_from_forward_backward_no_flip(self):
        """Teste sem inversão vertical"""
        forward = np.random.random((50, 50))
        backward = np.random.random((50, 50))
        
        topo = TopographyData.from_forward_backward(forward, backward, flip_vertical=False)
        
        expected = (forward + backward) / 2
        
        np.testing.assert_array_equal(topo.data, expected)
    
    def test_repr(self, sample_topography_data):
        """Teste de representação string"""
        repr_str = repr(sample_topography_data)
        
        assert "TopographyData" in repr_str
        assert "50, 50" in repr_str


@pytest.mark.integration
class TestTopographyDataIntegration:
    """Testes de integração para TopographyData"""
    
    def test_full_discretization_workflow(self, sample_topography_data):
        """Teste de workflow completo de discretização"""
        # 1. Discretizar
        sample_topography_data.discretize(10, 10)
        
        # 2. Selecionar blocos
        sample_topography_data.add_selected_block(0, 0)
        sample_topography_data.add_selected_block(1, 1)
        sample_topography_data.add_selected_block(2, 2)
        
        # 3. Obter máscara
        mask = sample_topography_data.get_selection_mask()
        
        # 4. Verificar valores
        for i in range(3):
            value = sample_topography_data.get_block_value(i, i)
            assert isinstance(value, (int, float, np.number))
        
        # Verificações finais
        assert sample_topography_data.discretized_data.shape == (5, 5)
        assert len(sample_topography_data.selected_blocks) == 3
        assert mask.sum() == 300  # 3 blocos * 100 pixels/bloco
    
    def test_save_load_preserve_discretization(self, sample_topography_data, temp_directory):
        """Teste que salvar/carregar preserva discretização"""
        # Discretizar e selecionar
        sample_topography_data.discretize(10, 10)
        sample_topography_data.add_selected_block(0, 0)
        
        # Salvar dados brutos
        filepath = temp_directory / "topo_with_disc.npy"
        sample_topography_data.save(str(filepath), format='npy')
        
        # Carregar
        loaded = TopographyData.load(str(filepath))
        
        # Dados brutos preservados
        np.testing.assert_array_equal(loaded.data, sample_topography_data.data)
        
        # Mas discretização não é preservada (é temporária)
        assert loaded.discretized_data is None
        assert len(loaded.selected_blocks) == 0
