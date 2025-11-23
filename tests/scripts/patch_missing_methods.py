"""
Patch para main_window.py - Adicionar métodos faltantes
Versão: 0.5.0 -> 0.5.1

Adiciona 3 métodos que estão conectados a botões mas não implementados:
1. truncate_range()
2. export_iv_data()
3. export_derivatives()
"""

METHODS_TO_ADD = """
    def truncate_range(self):
        \"\"\"Truncate spectral data to specified voltage range.\"\"\"
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        
        try:
            v_min = self.v_min_spin.value()
            v_max = self.v_max_spin.value()
            
            if v_min >= v_max:
                QMessageBox.warning(self, "Warning", "V min must be less than V max")
                return
            
            self.show_progress("Truncating data range...")
            
            # Truncate data
            self.spectral_data = self.spectral_data.truncate_range(v_min, v_max)
            
            self.hide_progress()
            self.update_ui_with_data()
            
            self.status_bar.showMessage(f"Data truncated to [{v_min:.3f}, {v_max:.3f}] V", 3000)
            logger.info(f"Data truncated to range [{v_min}, {v_max}]")
            
            QMessageBox.information(
                self,
                "Success",
                f"Data truncated to voltage range:\\n[{v_min:.3f}, {v_max:.3f}] V"
            )
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to truncate data: {str(e)}")
            logger.error(f"Error truncating data: {e}")
    
    def export_iv_data(self):
        \"\"\"Export I-V data with discretization.\"\"\"
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No spectral data available")
            return
        
        # Verify this is actually I-V data
        if self.current_data_type != 'iv':
            response = QMessageBox.question(
                self,
                "Confirm Export",
                f"Current data type is '{self.current_data_type}', not 'iv'.\\n"
                "Continue with export anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if response == QMessageBox.No:
                return
        
        try:
            self.show_progress("Exporting I-V data...")
            
            # Get discretization parameters
            block_h = self.block_h_spin.value()
            block_v = self.block_v_spin.value()
            use_selection = self.use_selection_check.isChecked()
            ignore_empty = self.ignore_empty_check.isChecked()
            
            # Get selected blocks if using selection
            selected_blocks = None
            if use_selection:
                if hasattr(self, 'topography_widget') and self.topography_data:
                    selected_blocks = self.topography_widget.get_selected_blocks()
                    if not selected_blocks:
                        QMessageBox.warning(self, "Warning", "No blocks selected for export")
                        self.hide_progress()
                        return
                else:
                    QMessageBox.warning(self, "Warning", "No topography data for block selection")
                    self.hide_progress()
                    return
            
            # Select output directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for I-V Export",
                "",
                QFileDialog.ShowDirsOnly
            )
            
            if not output_dir:
                self.hide_progress()
                return
            
            output_dir = Path(output_dir)
            
            # Perform discretization
            results = self.discretizer.discretize_spectral_data(
                spectral_data=self.spectral_data,
                block_h=block_h,
                block_v=block_v,
                topography=self.topography_data,
                selected_blocks=selected_blocks,
                ignore_empty_blocks=ignore_empty,
                data_type='iv'
            )
            
            # Save files
            intermediate_path = output_dir / "IV_intermediate.csv"
            final_path = output_dir / "IV_discretized.csv"
            
            results['intermediate'].save(str(intermediate_path))
            results['final'].save(str(final_path))
            
            # Also save statistics
            stats = self.discretizer.last_stats
            stats_path = output_dir / "IV_discretization_stats.txt"
            with open(stats_path, 'w') as f:
                f.write("I-V Data Discretization Statistics\\n")
                f.write("=" * 50 + "\\n\\n")
                for key, value in stats.items():
                    f.write(f"{key}: {value}\\n")
            
            self.hide_progress()
            
            message = f"I-V data exported successfully:\\n\\n"
            message += f"Intermediate: {intermediate_path.name}\\n"
            message += f"Final: {final_path.name}\\n"
            message += f"Statistics: {stats_path.name}"
            
            QMessageBox.information(self, "Export Complete", message)
            logger.info(f"I-V data exported to {output_dir}")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to export I-V data: {str(e)}")
            logger.error(f"Error exporting I-V data: {e}", exc_info=True)
    
    def export_derivatives(self):
        \"\"\"Export derivatives with discretization.\"\"\"
        if not self.derivatives:
            QMessageBox.warning(self, "Warning", "No derivatives available for export")
            return
        
        try:
            self.show_progress("Exporting derivatives...")
            
            # Get discretization parameters
            block_h = self.block_h_spin.value()
            block_v = self.block_v_spin.value()
            use_selection = self.use_selection_check.isChecked()
            ignore_empty = self.ignore_empty_check.isChecked()
            
            # Get selected blocks if using selection
            selected_blocks = None
            if use_selection:
                if hasattr(self, 'topography_widget') and self.topography_data:
                    selected_blocks = self.topography_widget.get_selected_blocks()
                    if not selected_blocks:
                        QMessageBox.warning(self, "Warning", "No blocks selected for export")
                        self.hide_progress()
                        return
                else:
                    QMessageBox.warning(self, "Warning", "No topography data for block selection")
                    self.hide_progress()
                    return
            
            # Select output directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for Derivatives Export",
                "",
                QFileDialog.ShowDirsOnly
            )
            
            if not output_dir:
                self.hide_progress()
                return
            
            output_dir = Path(output_dir)
            
            # Export each derivative type
            exported_files = []
            
            for deriv_name, deriv_data in self.derivatives.items():
                # Determine data type based on derivative name
                if 'first' in deriv_name:
                    data_type = 'didv'
                    prefix = "dIdV"
                elif 'second' in deriv_name:
                    data_type = 'd2idv2'
                    prefix = "d2IdV2"
                else:
                    data_type = 'unknown'
                    prefix = deriv_name
                
                # Add suffix for corrected derivatives
                if 'corrected' in deriv_name:
                    prefix += "_corrected"
                
                logger.info(f"Exporting {deriv_name} derivative as {prefix}")
                
                # Perform discretization
                results = self.discretizer.discretize_spectral_data(
                    spectral_data=deriv_data,
                    block_h=block_h,
                    block_v=block_v,
                    topography=self.topography_data,
                    selected_blocks=selected_blocks,
                    ignore_empty_blocks=ignore_empty,
                    data_type=data_type
                )
                
                # Save files
                intermediate_path = output_dir / f"{prefix}_intermediate.csv"
                final_path = output_dir / f"{prefix}_discretized.csv"
                
                results['intermediate'].save(str(intermediate_path))
                results['final'].save(str(final_path))
                
                exported_files.extend([intermediate_path.name, final_path.name])
            
            # Save statistics
            stats = self.discretizer.last_stats
            stats_path = output_dir / "derivatives_discretization_stats.txt"
            with open(stats_path, 'w') as f:
                f.write("Derivatives Discretization Statistics\\n")
                f.write("=" * 50 + "\\n\\n")
                f.write(f"Derivative types exported: {list(self.derivatives.keys())}\\n\\n")
                for key, value in stats.items():
                    f.write(f"{key}: {value}\\n")
            
            self.hide_progress()
            
            message = f"Derivatives exported successfully:\\n\\n"
            message += f"Total files: {len(exported_files)}\\n"
            message += f"Output directory: {output_dir}\\n\\n"
            message += "Files:\\n" + "\\n".join(f"  - {f}" for f in exported_files[:6])
            if len(exported_files) > 6:
                message += f"\\n  ... and {len(exported_files) - 6} more"
            
            QMessageBox.information(self, "Export Complete", message)
            logger.info(f"Derivatives exported to {output_dir}: {len(exported_files)} files")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to export derivatives: {str(e)}")
            logger.error(f"Error exporting derivatives: {e}", exc_info=True)
"""

if __name__ == '__main__':
    print("="*80)
    print("PATCH PARA main_window.py - Adicionar Métodos Faltantes")
    print("="*80)
    print()
    print("Este patch adiciona 3 métodos que estão conectados a botões mas não implementados:")
    print()
    print("1. truncate_range()")
    print("   - Trunca dados espectrais para um intervalo de voltagem")
    print("   - Conectado ao botão 'Truncate Range'")
    print()
    print("2. export_iv_data()")
    print("   - Exporta dados I-V discretizados")
    print("   - Conectado ao botão 'Export I-V'")
    print()
    print("3. export_derivatives()")
    print("   - Exporta derivadas discretizadas")
    print("   - Conectado ao botão 'Export Derivatives'")
    print()
    print("="*80)
    print("INSTRUÇÕES DE APLICAÇÃO")
    print("="*80)
    print()
    print("1. Localize a seção EXPORT METHODS em main_window.py")
    print("2. Adicione os métodos após export_topography_csv() (linha ~798)")
    print("3. Mantenha a indentação consistente (4 espaços)")
    print("4. Salve o arquivo")
    print("5. Teste cada funcionalidade")
    print()
    print("Os métodos completos estão na variável METHODS_TO_ADD deste arquivo.")
    print()
