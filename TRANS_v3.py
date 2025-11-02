import os
import numpy as np
import pandas as pd
import sys
from skimage.util import view_as_blocks
from skimage.measure import block_reduce
from scipy.signal import savgol_filter
import tkinter as tk
from tkinter import Tk, Toplevel, Label, Entry, Button, filedialog, messagebox, ttk, Button, Canvas, simpledialog
from NSFopen.read import read as nid_read
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
import tifffile


class TRANS:

    def _construir_cubo_meandro(self, data, dim_h, dim_v):
        """
        Rearranja os espectros adquiridos em MEANDRO 
        invertendo as linhas ímpares para ficar linha a linha.
        """
        n_pts, _ = data.shape
        cube = np.empty((n_pts, dim_v, dim_h), dtype=float)
        for row in range(dim_v):
            s = row * dim_h
            e = s + dim_h
            linha = data[:, s:e]
            if row % 2 == 1:
                linha = linha[:, ::-1]
            cube[:, row, :] = linha
        return cube

    def _mask_da_selecao(self, dim_h, dim_v, bloco_h, bloco_v):
        """
        Constrói a máscara 2D (dim_v x dim_h) a partir dos blocos selecionados no canvas.
        Cada retângulo selecionado cobre [bloco_v x bloco_h] posições no grid completo.
        """
        mask = np.zeros((dim_v, dim_h), dtype=bool)
        if not hasattr(self, "selecionados") or not hasattr(self, "blocos_canvas"):
            return mask
        for rid in list(self.selecionados):
            if rid not in self.blocos_canvas:
                continue
            i_blk, j_blk, _ = self.blocos_canvas[rid]
            r0 = i_blk * bloco_v
            r1 = min((i_blk + 1) * bloco_v, dim_v)
            c0 = j_blk * bloco_h
            c1 = min((j_blk + 1) * bloco_h, dim_h)
            mask[r0:r1, c0:c1] = True
        return mask

    def _exportar_discretizacao(self, data_df, nome_base, usar_selecao=False, ignorar_blocos_vazios=True, tipo_dados="auto"):
        """
        Rearranja os espectros adquiridos em MEANDRO 
        invertendo as linhas ímpares para ficar linha a linha.
        
        Agora suporta três tipos de dados:
        - "iv": Curvas I-V brutas
        - "didv": Primeira derivada (dI/dV)
        - "d2idv2": Segunda derivada (d²I/dV²)
        - "auto": Detecta automaticamente baseado no nome_base
        """
        import math

        # Validações para garantir que a tabela correta foi carregada
        if data_df is None or "V" not in data_df.columns:
            messagebox.showerror("Erro", "Tabela inválida (sem coluna 'V').")
            return None, None
        if not hasattr(self, "bloco_h") or not hasattr(self, "bloco_v"):
            messagebox.showerror("Erro", "Topografia ainda não foi discretizada (bloco_h/bloco_v).")
            return None, None
        if not hasattr(self, "dim_horizontal") or not hasattr(self, "dim_vertical"):
            messagebox.showerror("Erro", "Dimensões do grid (dim_horizontal/vertical) não definidas.")
            return None, None

        # Detectar tipo de dados automaticamente se necessário
        if tipo_dados == "auto":
            if "iv" in nome_base.lower() or "raw" in nome_base.lower() or "concatenated" in nome_base.lower():
                tipo_dados = "iv"
            elif "d2idv2" in nome_base.lower() or "second" in nome_base.lower() or "segunda" in nome_base.lower():
                tipo_dados = "d2idv2"
            else:
                tipo_dados = "didv"  # padrão

        V = data_df["V"].values
        data = data_df.drop(columns=["V"]).values
        n_pts, n_espectros = data.shape
        dim_h = int(self.dim_horizontal)
        dim_v = int(self.dim_vertical)
        esperado = dim_h * dim_v
                                                        
        if n_espectros != esperado:
            if n_espectros > esperado:
                data = data[:, :esperado]
                n_espectros = esperado
            else:
                if n_espectros < dim_h:
                    messagebox.showerror("Erro", f"Espectros ({n_espectros}) < dim_horizontal ({dim_h}).")
                    return None, None
                dim_v_eff = n_espectros // dim_h
                cols_used = dim_v_eff * dim_h
                if cols_used != n_espectros:
                    data = data[:, :cols_used]
                    n_espectros = cols_used
                dim_v = dim_v_eff

        # Meandro → linha-a-linha
        cube = self._construir_cubo_meandro(data, dim_h, dim_v)

        bloco_h = int(self.bloco_h)
        bloco_v = int(self.bloco_v)

        # manter/ignorar blocos vazios
        if hasattr(self, "manter_blocos_vazios"):
            ignorar_blocos_vazios = not bool(self.manter_blocos_vazios)

        # Seleção → máscara
        mask2d = None
        if usar_selecao:
            if not hasattr(self, "selecionados") or not hasattr(self, "blocos_canvas") or len(self.selecionados) == 0:
                messagebox.showerror("Erro", "Nenhum bloco selecionado na topografia.")
                return None, None
            mask2d = np.zeros((dim_v, dim_h), dtype=bool)
            for rid in list(self.selecionados):
                if rid not in self.blocos_canvas:
                    continue
                i_blk, j_blk, _ = self.blocos_canvas[rid]
                r0 = i_blk * bloco_v; r1 = min((i_blk + 1) * bloco_v, dim_v)
                c0 = j_blk * bloco_h; c1 = min((j_blk + 1) * bloco_h, dim_h)
                mask2d[r0:r1, c0:c1] = True
            # aplica a máscara no cubo (fora da seleção vira NaN)
            cube = cube.copy()
            cube[:, ~np.broadcast_to(mask2d[None, :, :], cube.shape)[0]] = np.nan

        # Etapas H→V
        num_grupos_h = int(math.ceil(dim_h / bloco_h))
        num_grupos_v = int(math.ceil(dim_v / bloco_v))

        # Aviso: bloco_v muito grande → 1 grupo vertical
        if num_grupos_v == 1 and bloco_v >= dim_v:
            messagebox.showwarning("Aviso",
                "bloco_v ≥ dim_vertical → apenas 1 grupo vertical. "
                "As colunas finais equivalem aos grupos horizontais cobertos.")

        # Média H (por linha, sem cruzar borda)
        h_avg = np.full((n_pts, dim_v, num_grupos_h), np.nan, dtype=float)
        for g in range(num_grupos_h):
            cs = g * bloco_h
            ce = min((g + 1) * bloco_h, dim_h)
            h_avg[:, :, g] = np.nanmean(cube[:, :, cs:ce], axis=2)

        # Intermediária: uma coluna por (linha y, grupo H g) que tenha dados
        cols_inter, mats_inter, skipped_h = [], [], 0
        for y in range(dim_v):
            for g in range(num_grupos_h):
                col = h_avg[:, y, g]
                vazio = np.all(np.isnan(col))
                if vazio and ignorar_blocos_vazios:
                    skipped_h += 1
                    continue
                mats_inter.append(col)
                # Nome mais descritivo baseado no tipo de dados
                if tipo_dados == "iv":
                    cols_inter.append(f"I_linha_{y}_hx_{g}")
                elif tipo_dados == "didv":
                    cols_inter.append(f"dIdV_linha_{y}_hx_{g}")
                elif tipo_dados == "d2idv2":
                    cols_inter.append(f"d2IdV2_linha_{y}_hx_{g}")
                else:
                    cols_inter.append(f"linha_{y}_hx_{g}")

        total_h_slots = dim_v * num_grupos_h
        if not mats_inter:
            messagebox.showwarning("Aviso", "Sem dados após a etapa horizontal (verifique seleção e blocos).")
            return None, None

        mat_inter = np.stack(mats_inter, axis=1)
        df_inter = pd.DataFrame(mat_inter, columns=cols_inter)
        df_inter.insert(0, "V", V)

        # Vertical: uma coluna por (grupo H g, grupo V j) que tenha dados
        cols_final, mats_final, lines_counts, skipped_v = [], [], [], 0
        bloco_idx = 0
        for g in range(num_grupos_h):
            for j in range(num_grupos_v):
                rs = j * bloco_v
                re = min((j + 1) * bloco_v, dim_v)
                fatia = h_avg[:, rs:re, g]  # (n_pts, altura)
                if ignorar_blocos_vazios and np.all(np.isnan(fatia)):
                    skipped_v += 1
                    continue
                medias = np.nanmean(fatia, axis=1)
                mats_final.append(medias)
                # Nome mais descritivo baseado no tipo de dados
                if tipo_dados == "iv":
                    cols_final.append(f"I_Bloco_{bloco_idx}")
                elif tipo_dados == "didv":
                    cols_final.append(f"dIdV_Bloco_{bloco_idx}")
                elif tipo_dados == "d2idv2":
                    cols_final.append(f"d2IdV2_Bloco_{bloco_idx}")
                else:
                    cols_final.append(f"Bloco_{bloco_idx}")
                lines_counts.append(int(re - rs))
                bloco_idx += 1

        if not mats_final:
            messagebox.showwarning("Aviso", "Sem dados após a etapa vertical (verifique bloco_v).")
            return df_inter, None

        mat_final = np.stack(mats_final, axis=1)
        df_final = pd.DataFrame(mat_final, columns=cols_final)
        df_final.insert(0, "V", V)

        outdir = self.output_dir if hasattr(self, "output_dir") else os.getcwd()
        
        # Nomes de arquivo mais descritivos baseados no tipo de dados
        if tipo_dados == "iv":
            path_inter = os.path.join(outdir, f"{nome_base}_IV_intermediaria.csv")
            path_final = os.path.join(outdir, f"{nome_base}_IV_discretizada.csv")
        elif tipo_dados == "didv":
            path_inter = os.path.join(outdir, f"{nome_base}_dIdV_intermediaria.csv")
            path_final = os.path.join(outdir, f"{nome_base}_dIdV_discretizada.csv")
        elif tipo_dados == "d2idv2":
            path_inter = os.path.join(outdir, f"{nome_base}_d2IdV2_intermediaria.csv")
            path_final = os.path.join(outdir, f"{nome_base}_d2IdV2_discretizada.csv")
        else:
            path_inter = os.path.join(outdir, f"{nome_base}_intermediaria.csv")
            path_final = os.path.join(outdir, f"{nome_base}_discretizada.csv")
        
        df_inter.to_csv(path_inter, index=False)
        df_final.to_csv(path_final, index=False)

        # Estatísticas para depuração/GUI
        if not hasattr(self, "last_discretizacao_stats"):
            self.last_discretizacao_stats = {}
        self.last_discretizacao_stats[nome_base] = {
            "tipo_dados": tipo_dados,
            "usar_selecao": bool(usar_selecao),
            "ignorar_blocos_vazios": bool(ignorar_blocos_vazios),
            "total_h_slots": int(total_h_slots),
            "inter_cols_geradas": int(len(cols_inter)),
            "inter_cols_ignoradas": int(skipped_h),
            "final_cols_geradas": int(len(cols_final)),
            "final_blocos_ignorados": int(skipped_v),
            "final_linhas_por_bloco": [int(x) for x in lines_counts],
            "grupos_h": int(num_grupos_h),
            "grupos_v": int(num_grupos_v),
        }
        return df_inter, df_final

    def read_and_process_table(self, input_file):
        """
        Processa tabela de dados I-V e calcula primeira e segunda derivadas.
        """
        try:
            df = pd.read_csv(input_file)
        except Exception as e:
            print(f"Erro ao carregar o arquivo {input_file}: {e}")
            return None, None

        V_values = df["V"].values
        I_values = df.drop(columns=["V"]).values

        smoothed_I_values = np.array([savgol_filter(col, window_length=11, polyorder=3) for col in I_values.T]).T

        V_diff = np.diff(V_values)
        first_derivative = (smoothed_I_values[2:, :] - smoothed_I_values[:-2, :]) / (V_diff[1:] + V_diff[:-1])[:, None]
        first_derivative = np.vstack([
            (smoothed_I_values[1, :] - smoothed_I_values[0, :]) / (V_values[1] - V_values[0]),
            first_derivative,
            (smoothed_I_values[-1, :] - smoothed_I_values[-2, :]) / (V_values[-1] - V_values[-2])
        ])

        smoothed_first_derivative = np.array([savgol_filter(col, window_length=11, polyorder=3) for col in first_derivative.T]).T

        second_derivative = (smoothed_first_derivative[2:, :] - smoothed_first_derivative[:-2, :]) / (V_diff[1:] + V_diff[:-1])[:, None]
        second_derivative = np.vstack([
            (smoothed_first_derivative[1, :] - smoothed_first_derivative[0, :]) / (V_values[1] - V_values[0]),
            second_derivative,
            (smoothed_first_derivative[-1, :] - smoothed_first_derivative[-2, :]) / (V_values[-1] - V_values[-2])
        ])

        smoothed_second_derivative = np.array([savgol_filter(col, window_length=11, polyorder=3) for col in second_derivative.T]).T

        df_first_derivative = pd.DataFrame(smoothed_first_derivative, columns=[f"File_{i+1}" for i in range(smoothed_first_derivative.shape[1])])
        df_first_derivative.insert(0, "V", V_values)

        df_second_derivative = pd.DataFrame(smoothed_second_derivative, columns=[f"File_{i+1}" for i in range(smoothed_second_derivative.shape[1])])
        df_second_derivative.insert(0, "V", V_values)

        directory_path = os.path.dirname(input_file)
        output_file_first_derivative = os.path.join(directory_path, "first_derivative.csv")
        output_file_second_derivative = os.path.join(directory_path, "second_derivative.csv")
        
        df_first_derivative.to_csv(output_file_first_derivative, index=False)
        df_second_derivative.to_csv(output_file_second_derivative, index=False)
        
        return df_first_derivative, df_second_derivative

    def integrate_over_intervals(self, intervals, data_frames):
        """
        Integra dados sobre intervalos de tensão especificados.
        """
        results = []
        for df in data_frames:
            V = df["V"].values
            integrated_data = []
            for interval in intervals:
                start, end = interval
                mask = (V >= start) & (V <= end)
                selected_data = df[mask]
                integrated = np.trapezoid(selected_data.drop(columns=["V"]).values, x=selected_data["V"].values, axis=0)
                integrated_data.append(integrated)
            results.append(pd.DataFrame(integrated_data).T)

        return results

    def create_map(self, dim_horizontal, dim_vertical, flattened_results, output_path):
        """
        Cria mapa de imagem a partir de resultados achatados.
        """
        try:
            map_data = np.zeros((dim_vertical, dim_horizontal))
            index = 0

            for row in range(dim_vertical):
                real_row = dim_vertical - row - 1
                if row % 2 == 0:
                    map_data[real_row, :] = flattened_results[index:index + dim_horizontal]
                else:
                    map_data[real_row, :] = flattened_results[index:index + dim_horizontal][::-1]
                index += dim_horizontal

            map_normalized = 255 * (map_data - np.min(map_data)) / (np.max(map_data) - np.min(map_data))
            map_normalized = map_normalized.astype(np.uint8)

            image = Image.fromarray(map_normalized) 
            image.save(output_path, format="TIFF")

            print(f"Mapa salvo em: {output_path}")
        except Exception as e:
            print(f"Erro ao criar o mapa: {e}")

    def get_user_parameters(self):
        """
        Obtém parâmetros do usuário para geração de mapas.
        """
        top = Toplevel(self.master)
        top.title("Configurações do Mapa e Intervalos")

        parameters = {"intervals": None, "dimensions": None}

        Label(top, text="Digite os intervalos (ex: -1.0,1.0;0.23,0.4):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        entry_intervals = Entry(top, width=50)
        entry_intervals.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        Label(top, text="Dimensão Horizontal:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        entry_horizontal = Entry(top, width=10)
        entry_horizontal.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        Label(top, text="Dimensão Vertical:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        entry_vertical = Entry(top, width=10)
        entry_vertical.grid(row=5, column=0, padx=10, pady=5, sticky="w")

        def save_and_close():
            try:
                raw_intervals = entry_intervals.get()
                if raw_intervals.strip():
                    intervals = [tuple(map(float, i.split(','))) for i in raw_intervals.split(';')]
                else:
                    raise ValueError("Os intervalos não podem estar vazios.")

                dim_horizontal = int(entry_horizontal.get())
                dim_vertical = int(entry_vertical.get())

                if dim_horizontal < 1 or dim_vertical < 1:
                    raise ValueError("Dimensões devem ser inteiros maiores ou iguais a 1.")

                parameters["intervals"] = intervals
                parameters["dimensions"] = (dim_horizontal, dim_vertical)

                top.quit()
                top.destroy()

            except Exception as e:
                messagebox.showerror("Erro", f"Entrada inválida: {e}")

        def cancel_and_close():
            parameters["intervals"] = None
            parameters["dimensions"] = None
            print("Operação cancelada pelo usuário.")
            top.quit()
            top.destroy()

        Button(top, text="Executar", command=save_and_close).grid(row=6, column=0, padx=10, pady=10, sticky="e")
        Button(top, text="Cancelar", command=cancel_and_close).grid(row=6, column=1, padx=10, pady=10, sticky="w")

        top.protocol("WM_DELETE_WINDOW", cancel_and_close)

        top.grab_set()
        top.focus_force()
        top.mainloop()
        return parameters

    def gerar_mapas_corrigidos_external(self, directory_path):
        """
        Gera mapas corrigidos a partir de arquivos .nid (função externa integrada).
        """
        top_avg_saved = False
        try:
            files = [f for f in os.listdir(directory_path) if f.endswith('.nid')]
            if not files:
                print("Nenhum arquivo .nid encontrado no diretório.")
                return

            files = sorted(files)
            for file_name in files:
                file_path = os.path.join(directory_path, file_name)
                if not top_avg_saved:
                    try:
                        stm_nid = nid_read(file_path)
                        top_forward = np.array(stm_nid.data.Image.Forward["Z-Axis"])
                        top_backward = np.array(stm_nid.data.Image.Backward["Z-Axis"])
                        top_avg = (top_forward + top_backward) / 2

                        # Normalizar para 0–255
                        top_norm = (top_avg - np.min(top_avg)) / (np.max(top_avg) - np.min(top_avg)) * 255
                        top_uint8 = top_norm.astype(np.uint8)
                        img = Image.fromarray(top_uint8)
                        # Espelhar verticalmente a topografia antes de salvar
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)
                        output_img_path = os.path.join(directory_path, "top_avg.tiff")
                        img.save(output_img_path)
                        
                        print(f"Imagem de topografia média salva como: {output_img_path}")
                        top_avg_saved = True
                        return img
                    except Exception as e:
                        print(f"Erro ao salvar topografia média de {file_name}: {e}")

        except Exception as e:
            print(f"Erro ao acessar o diretório {directory_path}: {e}")

    def processar_curvas_iv(self, df_iv):
        """
        Process raw I-V curves for discretization.
        This method can apply any necessary preprocessing to I-V data
        before discretization (smoothing, normalization, etc.)
        """
        V = df_iv["V"].values
        data = df_iv.drop(columns=["V"]).values
        
        # Apply smoothing to I-V curves (optional)
        smoothed_data = np.array([savgol_filter(col, window_length=11, polyorder=3) 
                                for col in data.T]).T
        
        df_processed = pd.DataFrame(smoothed_data, columns=df_iv.columns[1:])
        df_processed.insert(0, "V", V)
        
        return df_processed

    def __init__(self, master):
        self.master = master
        self.master.title("Análise de Topografia")
        self.master.geometry("650x900")

        self.imagem_topo = None
        self.dim_vertical = 0
        self.dim_horizontal = 0

        self.canvas_topografia = tk.Canvas(self.master, width=400, height=400, bg='white')
        self.blocos_canvas = {}      # id do retângulo → (i, j, valor)
        self.selecionados = set()    # conjunto de ids selecionados

        self.canvas_topografia.pack(pady=10)

        # Create main frame for buttons
        main_frame = tk.Frame(self.master)
        main_frame.pack(pady=10, fill='x', padx=10)

        # Column 1: Data Input
        col1 = tk.Frame(main_frame)
        col1.grid(row=0, column=0, padx=5, sticky='n')
        
        tk.Label(col1, text="Entrada de Dados", font=('Arial', 9, 'bold')).grid(row=0, column=0, pady=(0, 5))
        
        buttons_col1 = [
            ("Ler Arquivos .nid", self.read_and_concatenate_files),
            ("Carregar Topografia", self.carregar_topografia),
            ("Carregar Tabela", self.carregar_tabela_corrigida),
        ]
        
        for i, (text, command) in enumerate(buttons_col1, 1):
            btn = tk.Button(col1, text=text, command=command, width=18)
            btn.grid(row=i, column=0, pady=2, sticky='ew')

        # Column 2: Processing & Export
        col2 = tk.Frame(main_frame)
        col2.grid(row=0, column=1, padx=5, sticky='n')
        
        tk.Label(col2, text="Processamento", font=('Arial', 9, 'bold')).grid(row=0, column=0, pady=(0, 5))
        
        buttons_col2 = [
            ("Discretizar", self.discretizar_topografia),
            ("Truncar por V", self.truncar_por_intervalo_de_V),
            ("Exportar I-V", self.exportar_curvas_iv),
            ("Exportar Derivadas", self.exportar_derivadas_discretizadas),
            ("Exportar Seleção", self.exportar_selecao_para_csv),
        ]
        
        for i, (text, command) in enumerate(buttons_col2, 1):
            btn = tk.Button(col2, text=text, command=command, width=18)
            btn.grid(row=i, column=0, pady=2, sticky='ew')

        # Column 3: Visualization
        col3 = tk.Frame(main_frame)
        col3.grid(row=0, column=2, padx=5, sticky='n')
        
        tk.Label(col3, text="Visualização", font=('Arial', 9, 'bold')).grid(row=0, column=0, pady=(0, 5))
        
        buttons_col3 = [
            ("Mapas Corrigidos", self.gerar_mapas_corrigidos),
            ("Novos Mapas", lambda: self.repetir_integracao_e_mapa(
                self.first_derivative_df, self.second_derivative_df, self.output_dir)),
        ]
        
        for i, (text, command) in enumerate(buttons_col3, 1):
            btn = tk.Button(col3, text=text, command=command, width=18)
            btn.grid(row=i, column=0, pady=2, sticky='ew')

        # Close button at bottom
        close_frame = tk.Frame(self.master)
        close_frame.pack(pady=15)
        
        self.master.protocol("WM_DELETE_WINDOW", self.encerrar_programa)
        
    def carregar_tabela_corrigida(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a tabela corrigida (curvas I-V ou dI/dV)",
            filetypes=[("CSV files", "*.csv")]
        )

        if not caminho:
            return

        try:
            df_corrigido = pd.read_csv(caminho)
            
            # Get filename without path for detection
            filename = os.path.basename(caminho).lower()
            
            # Detect data type based on filename patterns
            V = df_corrigido["V"].values
            data_columns = [col for col in df_corrigido.columns if col != "V"]
            
            # Detection logic - simplified to use only filename patterns
            is_iv_data = (
                'iv' in filename or 
                'raw' in filename or 
                'current' in filename or
                'processed_data' in filename or
                'concatenated' in filename
            )
            
            is_first_derivative = (
                'didv' in filename or
                'first_derivative' in filename or
                'primeira_derivada' in filename or
                'correct_fit' in filename
            )

            if is_iv_data:
                # Loaded I-V curves - process to get derivatives
                messagebox.showinfo("Detectado", "Curvas I-V detectadas. Processando derivadas...")
                
                # Store the raw I-V data
                self.iv_raw_trunc_df = df_corrigido
                
                # Create a temporary file and use existing read_and_process_table method
                temp_file = os.path.join(os.path.dirname(caminho), "temp_iv_data.csv")
                df_corrigido.to_csv(temp_file, index=False)
                
                # Process to get derivatives using existing workflow
                self.first_derivative_df, self.second_derivative_df = self.read_and_process_table(temp_file)
                
                # Clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                # Store as corrected versions
                self.didv_corrigido_df = self.first_derivative_df
                self.d2idv2_corrigido_df = self.second_derivative_df
                
                # Save the derivatives for consistency
                output_dir = os.path.dirname(caminho)
                self.didv_corrigido_path = os.path.join(output_dir, "didv_from_iv_corrected.csv")
                self.d2idv2_corrigido_path = os.path.join(output_dir, "d2idv2_from_iv_corrected.csv")
                self.didv_corrigido_df.to_csv(self.didv_corrigido_path, index=False)
                self.d2idv2_corrigido_df.to_csv(self.d2idv2_corrigido_path, index=False)
                
            elif is_first_derivative:
                # First derivative data - current workflow
                messagebox.showinfo("Detectado", "Primeira derivada (dI/dV) detectada.")
                self.first_derivative_df = df_corrigido
                self.didv_corrigido_df = df_corrigido
                self.second_derivative_df = self.calcular_segunda_derivada(df_corrigido)
                self.d2idv2_corrigido_df = self.second_derivative_df
                
                # Save paths
                self.didv_corrigido_path = caminho
                self.d2idv2_corrigido_path = os.path.join(os.path.dirname(caminho), "d2idv2_calculated_from_loaded.csv")
                self.d2idv2_corrigido_df.to_csv(self.d2idv2_corrigido_path, index=False)
                
            else:
                # Ask user to specify type
                choice = messagebox.askquestion(
                    "Tipo de Dados", 
                    "Não foi possível detectar automaticamente o tipo de dados.\n\n"
                    "O arquivo contém:\n"
                    "• Curvas I-V brutas? (Clique 'Yes')\n" 
                    "• Primeira derivada (dI/dV)? (Clique 'No')",
                    icon='question'
                )
                
                if choice == 'yes':
                    # Treat as I-V data
                    messagebox.showinfo("Detectado", "Processando como curvas I-V...")
                    self.iv_raw_trunc_df = df_corrigido
                    
                    # Create temp file and process
                    temp_file = os.path.join(os.path.dirname(caminho), "temp_iv_data.csv")
                    df_corrigido.to_csv(temp_file, index=False)
                    self.first_derivative_df, self.second_derivative_df = self.read_and_process_table(temp_file)
                    
                    # Clean up
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        
                    self.didv_corrigido_df = self.first_derivative_df
                    self.d2idv2_corrigido_df = self.second_derivative_df
                else:
                    # Treat as first derivative
                    messagebox.showinfo("Detectado", "Processando como primeira derivada...")
                    self.first_derivative_df = df_corrigido
                    self.didv_corrigido_df = df_corrigido
                    self.second_derivative_df = self.calcular_segunda_derivada(df_corrigido)
                    self.d2idv2_corrigido_df = self.second_derivative_df

            # Set output directory and generate maps
            self.output_dir = os.path.dirname(caminho)
            
            # Check if we have the required data before generating maps
            if hasattr(self, "didv_corrigido_df") and hasattr(self, "d2idv2_corrigido_df"):
                self.gerar_mapas_corrigidos()
            else:
                messagebox.showwarning("Aviso", "Dados insuficientes para gerar mapas.")

            messagebox.showinfo("Tabela carregada", "Tabela carregada e processada com sucesso.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar a tabela: {e}")
            import traceback
            print(traceback.format_exc())  # For debugging
    def encerrar_programa(self):
        self.master.destroy()
        import sys
        sys.exit()

    def ajustar_derivadas_com_polinomios(self):
        try:
            if not hasattr(self, 'first_derivative_df') or not hasattr(self, 'second_derivative_df'):
                messagebox.showerror("Erro", "Derivadas não carregadas.")
                return

            V = self.first_derivative_df["V"].values

            def ajustar_polinomio(df, grau):
                corrigido = []
                for coluna in df.columns[1:]:
                    y = df[coluna].values
                    coef = np.polyfit(V, y, deg=grau)
                    ajuste = np.polyval(coef, V)
                    corrigido.append(y - ajuste)
                df_corrigido = pd.DataFrame(np.array(corrigido).T, columns=df.columns[1:])
                df_corrigido.insert(0, "V", V)
                return df_corrigido

            didv_corrigido = ajustar_polinomio(self.first_derivative_df, grau=2)
            d2idv2_corrigido = ajustar_polinomio(self.second_derivative_df, grau=4)

            caminho_base = self.output_dir if hasattr(self, 'output_dir') else "."

            self.didv_corrigido_path = os.path.join(caminho_base, "didv_correct_fit.csv")
            self.d2idv2_corrigido_path = os.path.join(caminho_base, "d2idv2_correct_fit.csv")

            didv_corrigido.to_csv(self.didv_corrigido_path, index=False)
            d2idv2_corrigido.to_csv(self.d2idv2_corrigido_path, index=False)

            self.didv_corrigido_df = didv_corrigido
            self.d2idv2_corrigido_df = d2idv2_corrigido

            messagebox.showinfo("Sucesso", "Tabelas corrigidas por ajuste polinomial salvas com sucesso.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ajustar curvas com polinômios: {e}")

    def calcular_segunda_derivada(self, df_primeira_derivada):
        V = df_primeira_derivada["V"].values
        data = df_primeira_derivada.drop(columns=["V"]).values

        d2I_dV2 = np.gradient(np.gradient(data, V, axis=0), V, axis=0)

        df_segunda = pd.DataFrame(d2I_dV2, columns=df_primeira_derivada.columns[1:])
        df_segunda.insert(0, "V", V)

        return df_segunda

    def read_and_concatenate_files(self):
        directory_path = filedialog.askdirectory(title="Selecione o diretório com arquivos .nid")
        if not directory_path:
            return

        concatenated_I = []
        V_common = None

        try:
            files = [f for f in os.listdir(directory_path) if f.endswith('.nid')]
            if not files:
                messagebox.showwarning("Aviso", "Nenhum arquivo .nid encontrado no diretório.")
                return

            files = sorted(files)
            for file_name in files:
                file_path = os.path.join(directory_path, file_name)
                try:
                    stm_nid = nid_read(file_path)
                    Ifor = np.array(stm_nid.data.Spec.Forward["Tip Current"])
                    Iback = np.array(stm_nid.data.Spec.Backward["Tip Current"])

                    Ifor_mean = np.mean(Ifor, axis=0)
                    Iback_mean = np.mean(Iback, axis=0)
                    I_mean = (Ifor_mean + Iback_mean) / 2
                    concatenated_I.append(I_mean)

                    V = np.array(stm_nid.data.Spec.Forward["Tip voltage"])[0, :]

                    if V_common is None:
                        V_common = V
                    elif not np.allclose(V_common, V):
                        messagebox.showerror("Erro", f"O vetor de tensões em {file_name} difere dos anteriores.")
                        return

                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao processar o arquivo {file_name}: {e}")

            if not concatenated_I or V_common is None:
                messagebox.showwarning("Aviso", "Nenhum dado processado.")
                return

            concatenated_I = np.array(concatenated_I)
            
            # Store raw I-V data
            df_raw = pd.DataFrame(concatenated_I.T, columns=[f"File_{i+1}" for i in range(concatenated_I.shape[0])])
            df_raw.insert(0, "V", V_common)
            self.iv_raw_df = df_raw  # Store raw I-V data

            # Solicita intervalo de truncamento
            vmin = simpledialog.askfloat("Intervalo de V", "Digite o valor mínimo de V:")
            vmax = simpledialog.askfloat("Intervalo de V", "Digite o valor máximo de V:")
            if vmin is None or vmax is None or vmin >= vmax:
                messagebox.showerror("Erro", "Intervalo inválido.")
                return

            V = df_raw["V"].values
            idx_min = (np.abs(V - vmin)).argmin()
            idx_max = (np.abs(V - vmax)).argmin()
            if idx_min > idx_max:
                idx_min, idx_max = idx_max, idx_min
            df_trunc = df_raw.iloc[idx_min:idx_max + 1]

            output_file = os.path.join(directory_path, "Processed_Data_with_V_truncado.csv")
            df_trunc.to_csv(output_file, index=False)

            # Store truncated raw data too
            self.iv_raw_trunc_df = df_trunc

            # Process derivatives using class method
            self.first_derivative_path = output_file
            self.first_derivative_df, self.second_derivative_df = self.read_and_process_table(output_file)
            
            self.ajustar_derivadas_com_polinomios()
            self.output_dir = os.path.dirname(output_file)

            messagebox.showinfo("Sucesso", f"Tabela truncada salva em:{output_file}")

            # Generate topography using class method
            topografia = self.gerar_mapas_corrigidos_external(directory_path)
            if topografia:
                self.imagem_topo = np.array(topografia)
                self.dim_vertical, self.dim_horizontal = self.imagem_topo.shape

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao acessar o diretório:{e}")

    def gerar_mapas_corrigidos(self):
        try:
            if not hasattr(self, "didv_corrigido_df") or not hasattr(self, "d2idv2_corrigido_df"):
                messagebox.showerror("Erro", "Tabelas corrigidas não estão carregadas.")
                return

            user_input = self.get_user_parameters()  # Use class method
            if not user_input["intervals"] or not user_input["dimensions"]:
                return

            intervals = user_input["intervals"]
            dimensions = user_input["dimensions"]
            dim_horizontal, dim_vertical = dimensions

            # Use class method for integration
            results = self.integrate_over_intervals(intervals, [self.didv_corrigido_df, self.d2idv2_corrigido_df])
            origins = ["Primeira Derivada Corrigida", "Segunda Derivada Corrigida"]

            output_dir = os.path.join(self.output_dir, "MapasCorrigidos")
            os.makedirs(output_dir, exist_ok=True)

            for idx, result in enumerate(results):
                flattened_results = result.values.flatten()
                origin_name = origins[idx].replace(" ", "_").lower()

                for interval_idx, interval in enumerate(intervals):
                    intervalo_str = f"({interval[0]},{interval[1]})".replace(".", "_")
                    mapa = result.iloc[:, interval_idx].values.flatten()
                    filename = f"{origin_name}_{intervalo_str}.tiff"
                    map_output_path = os.path.join(output_dir, filename)
                    # Use class method for map creation
                    self.create_map(dim_horizontal, dim_vertical, mapa, map_output_path)

            messagebox.showinfo("Concluído", "Mapas corrigidos gerados com sucesso.")

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar mapas corrigidos: {e}")

    def truncar_por_intervalo_de_V(self):
        if not hasattr(self, "first_derivative_df") or not hasattr(self, "second_derivative_df"):
            messagebox.showerror("Erro", "As tabelas de derivadas não estão carregadas.")
            return

        trunc_win = tk.Toplevel(self.master)
        trunc_win.title("Truncar dados por V")

        tk.Label(trunc_win, text="Valor mínimo de V:").grid(row=0, column=0, padx=10, pady=5)
        entry_vmin = tk.Entry(trunc_win)
        entry_vmin.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(trunc_win, text="Valor máximo de V:").grid(row=1, column=0, padx=10, pady=5)
        entry_vmax = tk.Entry(trunc_win)
        entry_vmax.grid(row=1, column=1, padx=10, pady=5)

        def executar_truncamento():
            try:
                vmin = float(entry_vmin.get())
                vmax = float(entry_vmax.get())

                if vmin >= vmax:
                    raise ValueError("O valor mínimo de V deve ser menor que o máximo.")

                for nome, df in [
                    ("first_derivative", self.first_derivative_df),
                    ("second_derivative", self.second_derivative_df),
                ]:
                    V = df["V"].values
                    idx_min = (np.abs(V - vmin)).argmin()
                    idx_max = (np.abs(V - vmax)).argmin()
                    if idx_min > idx_max:
                        idx_min, idx_max = idx_max, idx_min
                    df_trunc = df.iloc[idx_min:idx_max + 1]
                    caminho = os.path.join(self.output_dir, f"{nome}_truncado.csv")
                    df_trunc.to_csv(caminho, index=False)

                messagebox.showinfo("Concluído", f"Tabelas truncadas salvas em:\n{self.output_dir}")
                trunc_win.destroy()

            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao truncar: {e}")

        btn_exec = tk.Button(trunc_win, text="Executar", command=executar_truncamento)
        btn_exec.grid(row=2, column=0, columnspan=2, pady=10)

    def repetir_integracao_e_mapa(self, first_derivative, second_derivative, pasta_saida):
        user_input = self.get_user_parameters()  # Use class method

        if not user_input["intervals"] or not user_input["dimensions"]:
            print("Operação cancelada.")
            return

        intervals = user_input["intervals"]
        dimensions = user_input["dimensions"]
        dim_horizontal, dim_vertical = dimensions

        # Use class method for integration
        results = self.integrate_over_intervals(intervals, [first_derivative, second_derivative])
        origins = ["Primeira Derivada", "Segunda Derivada"]

        for idx, result in enumerate(results):
            flattened_results = result.values.flatten()
            origin_name = origins[idx].replace(" ", "_").lower()

            for interval_idx, interval in enumerate(intervals):
                intervalo_str = f"({interval[0]},{interval[1]})".replace(".", "_")
                mapa = result.iloc[:, interval_idx].values.flatten()
                filename = f"{origin_name}_{intervalo_str}.tiff"
                map_output_path = os.path.join(pasta_saida, filename)
                # Use class method for map creation
                self.create_map(dim_horizontal, dim_vertical, mapa, map_output_path)

        messagebox.showinfo("Concluído", "Mapas recriados com sucesso.")

    def carregar_topografia(self):
        caminho = filedialog.askopenfilename(filetypes=[("TIFF files", "*.tif"), ("Todos os arquivos", "*.*")])
        if not caminho:
            return

        imagem = tifffile.imread(caminho)

        if imagem.ndim > 2:
            imagem = imagem[0]

        self.imagem_topo = imagem
        self.dim_vertical, self.dim_horizontal = imagem.shape

        imagem_norm = (imagem - np.min(imagem)) / (np.max(imagem) - np.min(imagem)) * 255
        imagem_pil = Image.fromarray(imagem_norm.astype(np.uint8)).convert("L")
        imagem_resized = imagem_pil.resize((400, 400), Image.NEAREST)

        self.imagem_tk = ImageTk.PhotoImage(imagem_resized)
    
        self.canvas_topografia.delete("all")
        self.canvas_topografia.create_image(0, 0, anchor="nw", image=self.imagem_tk)

    def discretizar_topografia(self):
        if self.imagem_topo is None:
            messagebox.showerror("Erro", "Nenhuma imagem de topografia carregada.")
            return

        from PIL import Image

        while True:
            try:
                bloco_v = simpledialog.askinteger("Discretização - Vertical",
                                                  f"Dimensão vertical: {self.dim_vertical}\nDigite o tamanho do bloco VERTICAL:",
                                                  minvalue=1, maxvalue=self.dim_vertical)
                if bloco_v is None:
                    return

                bloco_h = simpledialog.askinteger("Discretização - Horizontal",
                                                  f"Dimensão horizontal: {self.dim_horizontal}\nDigite o tamanho do bloco HORIZONTAL:",
                                                  minvalue=1, maxvalue=self.dim_horizontal)
                if bloco_h is None:
                    return

                precisa_redimensionar = (
                    self.dim_vertical % bloco_v != 0 or self.dim_horizontal % bloco_h != 0
                )

                if precisa_redimensionar:
                    nova_v = (self.dim_vertical // bloco_v) * bloco_v
                    nova_h = (self.dim_horizontal // bloco_h) * bloco_h

                    # Redimensiona visualmente a imagem topo
                    imagem_pil = Image.fromarray(self.imagem_topo)
                    imagem_redimensionada = imagem_pil.resize((nova_h, nova_v), Image.BICUBIC)
                    self.imagem_topo = np.array(imagem_redimensionada)

                    # Atualiza dimensões
                    self.dim_vertical = nova_v
                    self.dim_horizontal = nova_h

                    messagebox.showinfo("Ajuste de resolução",
                                        f"A imagem foi redimensionada visualmente de {imagem_pil.width}x{imagem_pil.height} "
                                        f"para {nova_h}x{nova_v} para ajustar aos blocos.")

                self.bloco_v = bloco_v
                self.bloco_h = bloco_h
                break

            except Exception as e:
                messagebox.showerror("Erro", f"Entrada inválida: {e}")
                return

        nova_altura = self.bloco_v
        nova_largura = self.bloco_h
        imagem_discretizada = np.zeros((nova_altura, nova_largura))

        for i in range(nova_altura):
            for j in range(nova_largura):
                bloco = self.imagem_topo[i * self.bloco_v:(i + 1) * self.bloco_v,
                                         j * self.bloco_h:(j + 1) * self.bloco_h]
                imagem_discretizada[i, j] = np.mean(bloco)

        self.desenhar_blocos_interativos(imagem_discretizada)

    def desenhar_blocos_interativos(self, matriz_discretizada):
        self.canvas_topografia.delete("all")
        altura, largura = matriz_discretizada.shape
        self.grid_shape = (altura, largura)

        canvas_size = 400
        bloco_canvas_h = canvas_size // largura
        bloco_canvas_v = canvas_size // altura

        self.blocos_canvas = {}
        self.selecionados = set()

        self.matriz_discretizada = matriz_discretizada  # ok manter

        for i in range(altura):
            for j in range(largura):
                valor = matriz_discretizada[i, j]
                cor = int((valor - np.min(matriz_discretizada)) / np.ptp(matriz_discretizada) * 255)
                hex_color = f"#{cor:02x}{cor:02x}{cor:02x}"

                x0 = j * bloco_canvas_h
                y0 = i * bloco_canvas_v
                x1 = x0 + bloco_canvas_h
                y1 = y0 + bloco_canvas_v

                rect_id = self.canvas_topografia.create_rectangle(
                    x0, y0, x1, y1, fill=hex_color, outline="black"
                )
                self.blocos_canvas[rect_id] = (i, j, valor)

        self.canvas_topografia.bind("<Button-1>", self.on_bloco_click)

    def on_bloco_click(self, event):
        clicked = self.canvas_topografia.find_closest(event.x, event.y)[0]
        if clicked not in self.blocos_canvas:
            return

        if clicked in self.selecionados:
            self.selecionados.remove(clicked)
            # Redesenhar com cor original
            i, j, valor = self.blocos_canvas[clicked]
            cor = int((valor - np.min(self.matriz_discretizada)) / np.ptp(self.matriz_discretizada) * 255)
            hex_color = f"#{cor:02x}{cor:02x}{cor:02x}"
            self.canvas_topografia.itemconfig(clicked, fill=hex_color)
        else:
            self.selecionados.add(clicked)
            # Aplicar cor de seleção (exemplo: azul)
            self.canvas_topografia.itemconfig(clicked, fill="#1f77b4")

        # Opcional: mostrar info
        i, j, valor = self.blocos_canvas[clicked]
        print(f"Selecionado ({i}, {j}) → valor: {valor:.3f}")

    def exportar_derivadas_discretizadas(self, usar_selecao=False):
        """
        Exporta discretização (intermediária + final) para I-V, 1ª e 2ª derivadas.
        Prefere tabelas corrigidas quando existirem. Se usar_selecao=True,
        aplica apenas nos blocos selecionados.
        """
        # Lista de todos os tipos de dados para processar
        pares_dados = []
        
        # Adicionar dados I-V brutos se disponíveis
        if hasattr(self, "iv_raw_trunc_df"):
            # Process raw I-V data first
            iv_processed = self.processar_curvas_iv(self.iv_raw_trunc_df)
            pares_dados.append(("iv_processed", iv_processed, "iv"))
        
        # Adicionar derivadas
        if hasattr(self, "didv_corrigido_df") and hasattr(self, "d2idv2_corrigido_df"):
            pares_dados.append(("didv_corrigido", self.didv_corrigido_df, "didv"))
            pares_dados.append(("d2idv2_corrigido", self.d2idv2_corrigido_df, "d2idv2"))
        else:
            if hasattr(self, "first_derivative_df"):
                pares_dados.append(("primeira_derivada", self.first_derivative_df, "didv"))
            if hasattr(self, "second_derivative_df"):
                pares_dados.append(("segunda_derivada", self.second_derivative_df, "d2idv2"))
        
        if not pares_dados:
            messagebox.showerror("Erro", "Nenhum dado disponível para exportação.")
            return
        
        ok = False
        for nome, df, tipo in pares_dados:
            inter, fin = self._exportar_discretizacao(df, nome, usar_selecao=usar_selecao, tipo_dados=tipo)
            ok = ok or (inter is not None)
        
        if ok:
            alvo = "com seleção" if usar_selecao else "completa"
            tipos_exportados = [tipo for _, _, tipo in pares_dados]
            messagebox.showinfo("Exportado", 
                              f"Tabelas discretizadas ({alvo}) exportadas com sucesso.\n"
                              f"Tipos de dados: {', '.join(tipos_exportados)}")

    def exportar_derivada_discretizada(self, derivada_df, nome_saida_base):
        """
        Compatibilidade: exporta discretização para uma derivada específica
        (sem seleção), encaminhando para o motor único.
        """
        self._exportar_discretizacao(derivada_df, nome_saida_base, usar_selecao=False)

    def exportar_selecao_para_csv(self):
        """
        Compatibilidade: exporta discretização somente na seleção do usuário,
        para ambas as derivadas, reutilizando o motor único.
        """
        self.exportar_derivadas_discretizadas(usar_selecao=True)

    def exportar_curvas_iv(self, usar_selecao=False):
        """
        Export only I-V curves discretization
        """
        if not hasattr(self, "iv_raw_trunc_df"):
            messagebox.showerror("Erro", "Dados I-V brutos não disponíveis.")
            return
        
        # Process raw I-V data
        iv_processed = self.processar_curvas_iv(self.iv_raw_trunc_df)
        
        inter, fin = self._exportar_discretizacao(iv_processed, "iv_curves", 
                                                usar_selecao=usar_selecao, 
                                                tipo_dados="iv")
        
        if inter is not None:
            alvo = "com seleção" if usar_selecao else "completa"
            messagebox.showinfo("Exportado", f"Curvas I-V discretizadas ({alvo}) exportadas com sucesso.")


def main():
    root = Tk()
    root.withdraw()
    app_window = tk.Toplevel(root)
    app_gui = TRANS(app_window)
    root.mainloop()

if __name__ == "__main__":
    main()