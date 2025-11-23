# TRANS_beta - ML Features Implementation Plan
**Author:** Claude Code
**Date:** 2025-01-23
**Version:** 1.0

---

## 🎯 Overview

This document outlines the implementation plan for three machine learning features in TRANS_beta:

1. **Automatic Peak Detection & Map Generation** - Replaces manual integration interval selection
2. **Outlier Detection via Isolation Forest** - Removes spurious spectra from datasets
3. **Topography Clustering with Training Database** - Builds and uses a sample-based image database

---

# Feature 1: Peak Detection & Automatic Map Generation

## 📋 Purpose
Automatically detect peaks in baseline-corrected dI/dV curves and generate maps based on detected peak positions, eliminating the manual process of selecting integration intervals.

## 🏗️ Architecture

### New Module: `src/ml/peak_detector.py`

```python
class PeakDetector:
    """
    Automatic peak detection in spectral curves using signal processing
    and optional ML-based validation.
    """

    def __init__(self):
        self.detection_method = 'scipy'  # Options: 'scipy', 'wavelet', 'ml'
        self.min_prominence = 0.1  # Minimum peak prominence
        self.min_distance = 5      # Minimum distance between peaks (in points)
        self.adaptive_threshold = True

    def detect_peaks(self, spectrum: np.ndarray, voltage: np.ndarray) -> List[Peak]:
        """
        Detect peaks in a single spectrum.

        Returns:
        --------
        peaks : List[Peak]
            List of Peak objects with position, height, width, prominence
        """

    def detect_peaks_in_dataset(self, spectral_data: SpectralData) -> Dict[int, List[Peak]]:
        """
        Detect peaks across all spectra in dataset.
        Returns dict mapping spectrum_idx -> peaks
        """

    def cluster_peaks_globally(self, all_peaks: Dict[int, List[Peak]]) -> List[PeakCluster]:
        """
        Cluster peaks across all spectra to identify common features.
        Uses DBSCAN or hierarchical clustering on peak positions.
        """

    def generate_integration_intervals(self, peak_clusters: List[PeakCluster]) -> List[Tuple[float, float]]:
        """
        Convert peak clusters to integration intervals.
        Each cluster becomes an interval: [peak_center - width, peak_center + width]
        """

    def validate_peaks_ml(self, peaks: List[Peak], spectrum: np.ndarray) -> List[Peak]:
        """
        Optional ML-based peak validation using trained classifier.
        Filters out false positives.
        """
```

### Data Structures

```python
@dataclass
class Peak:
    """Represents a detected peak."""
    voltage_position: float      # Voltage at peak maximum
    height: float                 # Peak intensity
    prominence: float             # Peak prominence
    width: float                  # Peak width at half-maximum
    left_base: float             # Left integration boundary
    right_base: float            # Right integration boundary
    confidence: float = 1.0      # ML confidence score (optional)

@dataclass
class PeakCluster:
    """Cluster of peaks across multiple spectra."""
    center_voltage: float        # Average peak position
    voltage_std: float           # Standard deviation of positions
    avg_height: float            # Average peak height
    member_count: int            # Number of spectra with this peak
    integration_interval: Tuple[float, float]  # Recommended interval
```

## 🔧 Implementation Details

### Step 1: Peak Detection Algorithm
**Method:** scipy.signal.find_peaks with adaptive parameters

```python
from scipy.signal import find_peaks, peak_prominences, peak_widths

def detect_peaks_scipy(self, spectrum, voltage):
    # 1. Normalize spectrum
    normalized = (spectrum - np.min(spectrum)) / (np.ptp(spectrum) + 1e-10)

    # 2. Detect peaks with prominence threshold
    peak_indices, properties = find_peaks(
        normalized,
        prominence=self.min_prominence,
        distance=self.min_distance,
        width=2  # Minimum width
    )

    # 3. Calculate peak properties
    prominences = peak_prominences(normalized, peak_indices)[0]
    widths, width_heights, left_ips, right_ips = peak_widths(
        normalized, peak_indices, rel_height=0.5
    )

    # 4. Create Peak objects
    peaks = []
    for i, idx in enumerate(peak_indices):
        peak = Peak(
            voltage_position=voltage[idx],
            height=spectrum[idx],
            prominence=prominences[i],
            width=widths[i] * (voltage[1] - voltage[0]),  # Convert to voltage units
            left_base=voltage[int(left_ips[i])],
            right_base=voltage[int(right_ips[i])]
        )
        peaks.append(peak)

    return peaks
```

### Step 2: Global Peak Clustering
**Method:** DBSCAN on peak positions across all spectra

```python
from sklearn.cluster import DBSCAN

def cluster_peaks_globally(self, all_peaks: Dict[int, List[Peak]]):
    # Collect all peak positions
    positions = []
    peak_objects = []

    for spectrum_idx, peaks in all_peaks.items():
        for peak in peaks:
            positions.append(peak.voltage_position)
            peak_objects.append((spectrum_idx, peak))

    positions = np.array(positions).reshape(-1, 1)

    # Cluster peaks by position
    dbscan = DBSCAN(eps=0.05, min_samples=5)  # eps in voltage units
    labels = dbscan.fit_predict(positions)

    # Create PeakClusters
    clusters = []
    for label in set(labels):
        if label == -1:  # Skip noise
            continue

        cluster_positions = positions[labels == label].flatten()
        cluster_peaks = [peak_objects[i] for i, l in enumerate(labels) if l == label]

        cluster = PeakCluster(
            center_voltage=np.mean(cluster_positions),
            voltage_std=np.std(cluster_positions),
            avg_height=np.mean([p[1].height for p in cluster_peaks]),
            member_count=len(cluster_positions),
            integration_interval=(
                np.min(cluster_positions) - 0.02,  # Add margin
                np.max(cluster_positions) + 0.02
            )
        )
        clusters.append(cluster)

    return sorted(clusters, key=lambda c: c.center_voltage)
```

### Step 3: Automatic Map Generation

```python
def auto_generate_maps(self, spectral_data: SpectralData, output_dir: Path):
    """Full automatic pipeline."""

    # 1. Detect peaks in all spectra
    all_peaks = self.detect_peaks_in_dataset(spectral_data)

    # 2. Cluster peaks globally
    peak_clusters = self.cluster_peaks_globally(all_peaks)

    # 3. Generate integration intervals
    intervals = self.generate_integration_intervals(peak_clusters)

    # 4. Use existing MapGenerator
    map_gen = MapGenerator()
    map_gen.set_integration_intervals(intervals)
    integration_results = map_gen.integrate_over_intervals(spectral_data)

    # 5. Create maps for each peak
    for i, (interval_key, integrated_data) in enumerate(integration_results.items()):
        cluster = peak_clusters[i]
        filename = f"peak_{i+1}_V{cluster.center_voltage:.3f}"
        map_path = output_dir / filename
        map_gen.create_spatial_map(
            integrated_data,
            spectral_data.metadata.dimensions,
            map_path
        )

    return peak_clusters, intervals
```

## 🎨 UI Integration

### Location: `src/ui/main_window.py`

**Add to Processing Group:**
```python
# ML-Assisted Processing
ml_group = QGroupBox("🤖 ML-Assisted Analysis")
ml_layout = QVBoxLayout()

# Peak detection settings
peak_detect_layout = QHBoxLayout()
peak_detect_layout.addWidget(QLabel("Min Prominence:"))
self.peak_prominence_spin = QDoubleSpinBox()
self.peak_prominence_spin.setRange(0.01, 1.0)
self.peak_prominence_spin.setValue(0.1)
self.peak_prominence_spin.setSingleStep(0.01)
peak_detect_layout.addWidget(self.peak_prominence_spin)

self.auto_peak_detect_btn = QPushButton("🎯 Auto-Detect Peaks")
self.auto_peak_detect_btn.clicked.connect(self.auto_detect_peaks)
ml_layout.addWidget(self.auto_peak_detect_btn)

self.show_peaks_btn = QPushButton("👁️ Visualize Detected Peaks")
self.show_peaks_btn.clicked.connect(self.visualize_peaks)
self.show_peaks_btn.setEnabled(False)
ml_layout.addWidget(self.show_peaks_btn)

self.auto_gen_maps_btn = QPushButton("🗺️ Auto-Generate Peak Maps")
self.auto_gen_maps_btn.clicked.connect(self.auto_generate_peak_maps)
self.auto_gen_maps_btn.setEnabled(False)
ml_layout.addWidget(self.auto_gen_maps_btn)

ml_group.setLayout(ml_layout)
```

**New Methods:**
```python
def auto_detect_peaks(self):
    """Detect peaks automatically in corrected dI/dV."""
    if "corrected" not in self.derivatives:
        QMessageBox.warning(
            self, "Warning",
            "Please calculate baseline-corrected derivatives first."
        )
        return

    self.show_progress("Detecting peaks...")

    try:
        self.peak_detector = PeakDetector()
        self.peak_detector.min_prominence = self.peak_prominence_spin.value()

        # Detect peaks
        self.detected_peaks = self.peak_detector.detect_peaks_in_dataset(
            self.derivatives["corrected"]
        )

        # Cluster globally
        self.peak_clusters = self.peak_detector.cluster_peaks_globally(
            self.detected_peaks
        )

        self.hide_progress()

        QMessageBox.information(
            self,
            "Peaks Detected",
            f"Found {len(self.peak_clusters)} distinct peak features\n"
            f"across {len(self.detected_peaks)} spectra."
        )

        self.show_peaks_btn.setEnabled(True)
        self.auto_gen_maps_btn.setEnabled(True)

    except Exception as e:
        self.hide_progress()
        QMessageBox.critical(self, "Error", f"Peak detection failed:\n{str(e)}")

def visualize_peaks(self):
    """Show detected peaks on curve plot."""
    # Add peak markers to existing curve visualization
    # Use vertical lines or markers at peak positions

def auto_generate_peak_maps(self):
    """Generate maps for all detected peak clusters."""
    output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
    if not output_dir:
        return

    self.show_progress("Generating maps...")

    try:
        peak_clusters, intervals = self.peak_detector.auto_generate_maps(
            self.derivatives["corrected"],
            Path(output_dir)
        )

        self.hide_progress()

        QMessageBox.information(
            self,
            "Maps Generated",
            f"Created {len(peak_clusters)} maps at:\n{output_dir}"
        )

    except Exception as e:
        self.hide_progress()
        QMessageBox.critical(self, "Error", f"Map generation failed:\n{str(e)}")
```

## 📊 Visualization

**Peak Overlay on Curves:**
```python
# In update_spectrum_plot(), after plotting curve:
if hasattr(self, 'detected_peaks') and self.show_peaks_checkbox.isChecked():
    # Get peaks for selected blocks
    for h_group, v_group in selected_blocks:
        block_idx = h_group * n_blocks_v + v_group
        if block_idx in self.detected_peaks:
            peaks = self.detected_peaks[block_idx]
            for peak in peaks:
                ax.axvline(peak.voltage_position, color='red',
                          linestyle='--', alpha=0.5, linewidth=1)
                ax.plot(peak.voltage_position, peak.height,
                       'ro', markersize=8)
```

## 🔬 Advanced: ML-Based Peak Validation (Optional Phase 2)

**Train a classifier to validate peaks:**
```python
class PeakValidationModel:
    """
    CNN or Random Forest to classify real peaks vs noise.

    Features:
    - Peak shape (extracted window around peak)
    - Peak prominence
    - Peak width
    - Symmetry
    - Local baseline characteristics
    """

    def extract_features(self, peak: Peak, spectrum: np.ndarray, voltage: np.ndarray):
        """Extract features for classification."""

    def train(self, labeled_peaks: List[Tuple[Peak, bool]]):
        """Train on user-labeled peaks."""

    def predict(self, peak: Peak) -> float:
        """Return confidence score [0, 1]."""
```

## 📦 Dependencies

Add to `requirements.txt`:
```
scipy>=1.10.0
scikit-learn>=1.3.0
```

---

# Feature 2: Outlier Detection with Isolation Forest

## 📋 Purpose
Automatically detect and remove spurious/anomalous spectra from raw STS datasets before processing, improving data quality and reducing noise in derived quantities.

## 🏗️ Architecture

### New Module: `src/ml/outlier_detector.py`

```python
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class OutlierDetector:
    """
    Detects outlier spectra using Isolation Forest algorithm.
    """

    def __init__(self):
        self.contamination = 0.05  # Expected fraction of outliers (5%)
        self.scaler = StandardScaler()
        self.model = None

    def detect_outliers(self,
                       spectral_data: SpectralData,
                       method: str = 'isolation_forest') -> Dict:
        """
        Detect outlier spectra in dataset.

        Parameters:
        -----------
        spectral_data : SpectralData
            Dataset to analyze
        method : str
            'isolation_forest', 'statistical', or 'combined'

        Returns:
        --------
        results : Dict
            {
                'outlier_indices': List[int],
                'outlier_scores': np.ndarray,
                'threshold': float,
                'n_outliers': int,
                'outlier_fraction': float
            }
        """

    def remove_outliers(self,
                       spectral_data: SpectralData,
                       outlier_indices: List[int]) -> SpectralData:
        """
        Create new SpectralData with outliers removed.
        """

    def visualize_outliers(self,
                          spectral_data: SpectralData,
                          outlier_indices: List[int],
                          method: str = 'pca'):
        """
        Visualize outliers using dimensionality reduction.
        method: 'pca', 'tsne', or 'umap'
        """
```

## 🔧 Implementation Details

### Feature Extraction

**Multiple feature sets for robustness:**

```python
def extract_features(self, spectral_data: SpectralData) -> np.ndarray:
    """
    Extract features from spectra for outlier detection.

    Features (per spectrum):
    1. Statistical moments: mean, std, skewness, kurtosis
    2. Spectral shape: peak positions, widths, number of peaks
    3. Noise level: high-frequency component energy
    4. Derivative features: smoothness, discontinuities
    5. Raw spectral values (optionally, PCA-reduced)
    """

    spectra = spectral_data.spectra.values.T  # (n_spectra, n_points)
    n_spectra = spectra.shape[0]

    features = []

    for i in range(n_spectra):
        spectrum = spectra[i]

        # Statistical moments
        mean = np.mean(spectrum)
        std = np.std(spectrum)
        skew = scipy.stats.skew(spectrum)
        kurt = scipy.stats.kurtosis(spectrum)

        # Range and variance
        ptp = np.ptp(spectrum)

        # Derivative features (smoothness)
        deriv = np.diff(spectrum)
        deriv_std = np.std(deriv)

        # High-frequency noise (using wavelet decomposition)
        noise_level = estimate_noise_level(spectrum)

        # Peak count
        peaks = find_peaks(spectrum, prominence=0.1)[0]
        n_peaks = len(peaks)

        # Combine features
        feature_vector = [
            mean, std, skew, kurt, ptp,
            deriv_std, noise_level, n_peaks
        ]

        features.append(feature_vector)

    return np.array(features)

def estimate_noise_level(spectrum):
    """Estimate noise using wavelet decomposition."""
    from scipy import signal

    # High-pass filter to isolate noise
    b, a = signal.butter(4, 0.3, btype='high')
    noise = signal.filtfilt(b, a, spectrum)
    return np.std(noise)
```

### Isolation Forest Implementation

```python
def detect_outliers_isolation_forest(self, spectral_data: SpectralData):
    # Extract features
    features = self.extract_features(spectral_data)

    # Normalize features
    features_scaled = self.scaler.fit_transform(features)

    # Train Isolation Forest
    self.model = IsolationForest(
        contamination=self.contamination,
        n_estimators=100,
        max_samples='auto',
        random_state=42,
        n_jobs=-1
    )

    # Predict outliers (-1 = outlier, 1 = inlier)
    predictions = self.model.fit_predict(features_scaled)

    # Get anomaly scores (lower = more anomalous)
    scores = self.model.score_samples(features_scaled)

    # Identify outlier indices
    outlier_indices = np.where(predictions == -1)[0].tolist()

    return {
        'outlier_indices': outlier_indices,
        'outlier_scores': scores,
        'predictions': predictions,
        'n_outliers': len(outlier_indices),
        'outlier_fraction': len(outlier_indices) / len(predictions)
    }
```

### Statistical Fallback Method

```python
def detect_outliers_statistical(self, spectral_data: SpectralData):
    """
    Z-score based outlier detection (simpler, no ML required).
    """
    features = self.extract_features(spectral_data)

    # Calculate z-scores for each feature
    z_scores = np.abs(scipy.stats.zscore(features, axis=0))

    # Mark as outlier if ANY feature has z-score > threshold
    threshold = 3.0
    outlier_mask = np.any(z_scores > threshold, axis=1)
    outlier_indices = np.where(outlier_mask)[0].tolist()

    return {
        'outlier_indices': outlier_indices,
        'outlier_scores': -np.max(z_scores, axis=1),  # Negative for consistency
        'n_outliers': len(outlier_indices),
        'outlier_fraction': len(outlier_indices) / len(outlier_mask)
    }
```

### Outlier Removal

```python
def remove_outliers(self, spectral_data: SpectralData, outlier_indices: List[int]):
    """Create cleaned dataset."""

    # Get column names (skip first column which is voltage)
    all_columns = spectral_data.data.columns[1:]  # Skip 'V' column

    # Identify columns to keep (inliers)
    inlier_columns = [col for i, col in enumerate(all_columns)
                     if i not in outlier_indices]

    # Create new dataframe with voltage + inlier spectra
    cleaned_df = spectral_data.data[['V'] + inlier_columns].copy()

    # Update metadata
    new_metadata = spectral_data.metadata
    # Note: dimensions might need adjustment if grid-based

    # Create new SpectralData
    cleaned_data = SpectralData(cleaned_df, new_metadata, spectral_data.topography)

    logger.info(f"Removed {len(outlier_indices)} outlier spectra")
    logger.info(f"Cleaned dataset: {cleaned_data.num_spectra} spectra remaining")

    return cleaned_data
```

## 🎨 UI Integration

### Location: Add to Preprocessing group

```python
# Outlier Detection (in preprocessing group)
outlier_group = QGroupBox("🔍 Outlier Detection")
outlier_layout = QVBoxLayout()

contamination_layout = QHBoxLayout()
contamination_layout.addWidget(QLabel("Expected Outliers:"))
self.contamination_spin = QDoubleSpinBox()
self.contamination_spin.setRange(0.01, 0.20)
self.contamination_spin.setValue(0.05)
self.contamination_spin.setSingleStep(0.01)
self.contamination_spin.setSuffix("%")
contamination_layout.addWidget(self.contamination_spin)
outlier_layout.addLayout(contamination_layout)

self.detect_outliers_btn = QPushButton("🎯 Detect Outliers")
self.detect_outliers_btn.clicked.connect(self.detect_outliers)
outlier_layout.addWidget(self.detect_outliers_btn)

self.visualize_outliers_btn = QPushButton("📊 Visualize Outliers")
self.visualize_outliers_btn.clicked.connect(self.visualize_outliers)
self.visualize_outliers_btn.setEnabled(False)
outlier_layout.addWidget(self.visualize_outliers_btn)

self.remove_outliers_btn = QPushButton("🗑️ Remove Outliers")
self.remove_outliers_btn.clicked.connect(self.remove_outliers)
self.remove_outliers_btn.setEnabled(False)
outlier_layout.addWidget(self.remove_outliers_btn)

outlier_group.setLayout(outlier_layout)
```

### New Methods

```python
def detect_outliers(self):
    """Detect outliers in loaded data."""
    if self.spectral_data is None:
        QMessageBox.warning(self, "Warning", "No data loaded")
        return

    self.show_progress("Detecting outliers...")

    try:
        self.outlier_detector = OutlierDetector()
        self.outlier_detector.contamination = self.contamination_spin.value() / 100

        self.outlier_results = self.outlier_detector.detect_outliers(
            self.spectral_data,
            method='isolation_forest'
        )

        self.hide_progress()

        n_outliers = self.outlier_results['n_outliers']
        fraction = self.outlier_results['outlier_fraction'] * 100

        msg = f"Detected {n_outliers} outlier spectra ({fraction:.1f}%)\n\n"
        msg += "Would you like to visualize them?"

        reply = QMessageBox.question(
            self, "Outliers Detected", msg,
            QMessageBox.Yes | QMessageBox.No
        )

        self.visualize_outliers_btn.setEnabled(True)
        self.remove_outliers_btn.setEnabled(True)

        if reply == QMessageBox.Yes:
            self.visualize_outliers()

    except Exception as e:
        self.hide_progress()
        QMessageBox.critical(self, "Error", f"Outlier detection failed:\n{str(e)}")

def visualize_outliers(self):
    """Show outliers in PCA/t-SNE space."""
    if not hasattr(self, 'outlier_results'):
        return

    # Create visualization dialog
    dialog = QDialog(self)
    dialog.setWindowTitle("Outlier Visualization")
    dialog.setMinimumSize(800, 600)

    layout = QVBoxLayout(dialog)

    # Create matplotlib figure
    fig = Figure(figsize=(10, 8))
    canvas = FigureCanvas(fig)
    layout.addWidget(canvas)

    # PCA projection
    from sklearn.decomposition import PCA
    features = self.outlier_detector.extract_features(self.spectral_data)
    pca = PCA(n_components=2)
    projected = pca.fit_transform(features)

    # Plot
    ax = fig.add_subplot(111)

    inliers = [i for i in range(len(projected))
              if i not in self.outlier_results['outlier_indices']]
    outliers = self.outlier_results['outlier_indices']

    ax.scatter(projected[inliers, 0], projected[inliers, 1],
              c='blue', label='Inliers', alpha=0.6, s=30)
    ax.scatter(projected[outliers, 0], projected[outliers, 1],
              c='red', label='Outliers', alpha=0.8, s=50, marker='x')

    ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)')
    ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)')
    ax.set_title('Outlier Detection: PCA Projection')
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    canvas.draw()

    # Show dialog
    dialog.exec()

def remove_outliers(self):
    """Remove detected outliers from dataset."""
    if not hasattr(self, 'outlier_results'):
        return

    n_outliers = self.outlier_results['n_outliers']

    reply = QMessageBox.question(
        self,
        "Confirm Removal",
        f"Remove {n_outliers} outlier spectra?\n\n"
        "This cannot be undone. Original data will be replaced.",
        QMessageBox.Yes | QMessageBox.No
    )

    if reply != QMessageBox.Yes:
        return

    try:
        self.show_progress("Removing outliers...")

        # Create cleaned dataset
        cleaned_data = self.outlier_detector.remove_outliers(
            self.spectral_data,
            self.outlier_results['outlier_indices']
        )

        # Replace current data
        self.spectral_data = cleaned_data

        # Clear derivatives (need to recalculate)
        self.derivatives = {}

        # Update UI
        self.update_ui_with_data()

        self.hide_progress()

        QMessageBox.information(
            self,
            "Outliers Removed",
            f"Dataset cleaned.\n"
            f"Remaining: {cleaned_data.num_spectra} spectra\n\n"
            f"Please recalculate derivatives if needed."
        )

    except Exception as e:
        self.hide_progress()
        QMessageBox.critical(self, "Error", f"Failed to remove outliers:\n{str(e)}")
```

## 📊 Visualization Options

### 1. PCA/t-SNE Scatter Plot (implemented above)
### 2. Heatmap of Anomaly Scores
### 3. Outlier Spectra Overlay

```python
def plot_outlier_spectra_comparison(self):
    """Show average inlier vs average outlier spectrum."""

    inlier_indices = [i for i in range(self.spectral_data.num_spectra)
                     if i not in self.outlier_results['outlier_indices']]
    outlier_indices = self.outlier_results['outlier_indices']

    V = self.spectral_data.independent_var
    spectra = self.spectral_data.spectra.values

    avg_inlier = np.mean(spectra[:, inlier_indices], axis=1)
    avg_outlier = np.mean(spectra[:, outlier_indices], axis=1)

    ax.plot(V, avg_inlier, 'b-', label='Average Inlier', linewidth=2)
    ax.plot(V, avg_outlier, 'r-', label='Average Outlier', linewidth=2, alpha=0.7)
    ax.legend()
```

## 📦 Dependencies

```
scikit-learn>=1.3.0
scipy>=1.10.0
```

---

# Feature 3: Topography Clustering with Training Database

## 📋 Purpose
Build a sample-based database of topography images from multiple .nid files, train clustering models once sufficient data is available, and automatically classify new topographies.

## 🏗️ Architecture

### New Modules

#### `src/ml/topography_database.py`

```python
class TopographyDatabase:
    """
    Manages a persistent database of topography images organized by sample.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path.home() / '.trans' / 'topography_db.sqlite'
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self.conn = None
        self._initialize_database()

    def add_sample(self, sample_name: str, description: str = ""):
        """Add a new sample to the database."""

    def add_topography(self,
                      sample_name: str,
                      topo_data: TopographyData,
                      metadata: Dict,
                      source_file: Path):
        """Add a topography image to a sample."""

    def get_sample_statistics(self) -> pd.DataFrame:
        """Get statistics about samples and image counts."""

    def get_all_topographies(self, sample_name: str = None) -> List[Dict]:
        """Retrieve topographies, optionally filtered by sample."""

    def export_for_training(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Export data for ML training.

        Returns:
        --------
        images : np.ndarray
            Shape (n_images, height, width) - preprocessed and normalized
        labels : np.ndarray
            Shape (n_images,) - sample indices
        """

    def is_training_ready(self, min_samples: int = 3, min_images_per_sample: int = 10) -> bool:
        """Check if database has enough data for training."""
```

#### `src/ml/topography_clusterer.py`

```python
class TopographyClusterer:
    """
    Clustering and classification of topography images.
    """

    def __init__(self):
        self.feature_extractor = None  # CNN or traditional features
        self.clusterer = None          # KMeans, DBSCAN, etc.
        self.classifier = None         # Optional supervised classifier
        self.scaler = StandardScaler()

    def extract_features(self, topo_data: np.ndarray) -> np.ndarray:
        """
        Extract features from topography image.

        Methods:
        1. Traditional: texture features (Haralick, LBP), statistical moments
        2. Deep learning: CNN embeddings (ResNet, VGG)
        """

    def train_clustering(self,
                        database: TopographyDatabase,
                        n_clusters: int = None,
                        method: str = 'kmeans'):
        """
        Train unsupervised clustering model.

        Parameters:
        -----------
        database : TopographyDatabase
            Source of training data
        n_clusters : int
            Number of clusters (None = auto-determine)
        method : str
            'kmeans', 'dbscan', 'hierarchical'
        """

    def train_classifier(self, database: TopographyDatabase):
        """
        Train supervised classifier using sample labels.

        Uses sample_name as class label.
        """

    def predict(self, topo_data: TopographyData) -> Dict:
        """
        Predict cluster/class for new topography.

        Returns:
        --------
        prediction : Dict
            {
                'cluster_id': int,
                'confidence': float,
                'nearest_samples': List[str],  # Most similar samples
                'distance_to_centroid': float
            }
        """
```

### Database Schema (SQLite)

```sql
CREATE TABLE samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_count INTEGER DEFAULT 0
);

CREATE TABLE topographies (
    topo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL,
    source_file TEXT,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Image data (stored as BLOB or HDF5 reference)
    image_data BLOB,

    -- Dimensions
    width INTEGER,
    height INTEGER,

    -- Physical dimensions
    physical_width_nm REAL,
    physical_height_nm REAL,

    -- Metadata (JSON)
    metadata TEXT,

    -- Extracted features (for quick retrieval)
    features BLOB,

    FOREIGN KEY (sample_id) REFERENCES samples(sample_id)
);

CREATE INDEX idx_sample ON topographies(sample_id);
```

## 🔧 Implementation Details

### Feature Extraction Methods

#### Option 1: Traditional Image Features

```python
def extract_traditional_features(self, topo_image: np.ndarray) -> np.ndarray:
    """
    Extract traditional image features.

    Features:
    1. Statistical moments (mean, std, skewness, kurtosis)
    2. Texture features (Haralick from GLCM)
    3. Local Binary Patterns (LBP)
    4. Gradient statistics
    5. Fourier spectrum features
    """

    from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

    features = []

    # 1. Statistical moments
    features.extend([
        np.mean(topo_image),
        np.std(topo_image),
        scipy.stats.skew(topo_image.flatten()),
        scipy.stats.kurtosis(topo_image.flatten()),
        np.ptp(topo_image)  # Range
    ])

    # 2. Normalize for texture analysis
    normalized = ((topo_image - np.min(topo_image)) /
                 (np.ptp(topo_image) + 1e-10) * 255).astype(np.uint8)

    # 3. GLCM texture features
    glcm = graycomatrix(normalized, distances=[1], angles=[0, np.pi/4, np.pi/2, 3*np.pi/4],
                       levels=256, symmetric=True, normed=True)

    for prop in ['contrast', 'dissimilarity', 'homogeneity', 'energy', 'correlation']:
        features.append(np.mean(graycoprops(glcm, prop)))

    # 4. Local Binary Patterns
    lbp = local_binary_pattern(normalized, P=8, R=1, method='uniform')
    lbp_hist, _ = np.histogram(lbp, bins=10, range=(0, 10), density=True)
    features.extend(lbp_hist)

    # 5. Gradient features
    gy, gx = np.gradient(topo_image)
    gradient_mag = np.sqrt(gx**2 + gy**2)
    features.extend([
        np.mean(gradient_mag),
        np.std(gradient_mag)
    ])

    # 6. Fourier features (power spectrum)
    fft = np.fft.fft2(topo_image)
    power_spectrum = np.abs(fft)**2
    # Radial average
    features.append(np.mean(power_spectrum))

    return np.array(features)
```

#### Option 2: Deep Learning Features (More Advanced)

```python
def extract_cnn_features(self, topo_image: np.ndarray) -> np.ndarray:
    """
    Extract features using pre-trained CNN.

    Uses transfer learning from ResNet/VGG trained on ImageNet.
    """

    from tensorflow.keras.applications import ResNet50
    from tensorflow.keras.applications.resnet50 import preprocess_input
    from tensorflow.keras.preprocessing import image

    # Load pre-trained model (without top classification layer)
    if self.feature_extractor is None:
        self.feature_extractor = ResNet50(
            weights='imagenet',
            include_top=False,
            pooling='avg'
        )

    # Preprocess image
    # Convert to 3-channel (ResNet expects RGB)
    img_resized = cv2.resize(topo_image, (224, 224))
    img_rgb = np.stack([img_resized]*3, axis=-1)
    img_array = np.expand_dims(img_rgb, axis=0)
    img_preprocessed = preprocess_input(img_array)

    # Extract features
    features = self.feature_extractor.predict(img_preprocessed, verbose=0)

    return features.flatten()
```

### Clustering Implementation

```python
def train_clustering_kmeans(self, images, n_clusters=None):
    """Train K-Means clustering."""

    # Extract features for all images
    features = np.array([self.extract_features(img) for img in images])

    # Normalize
    features_scaled = self.scaler.fit_transform(features)

    # Determine optimal k if not specified
    if n_clusters is None:
        n_clusters = self._find_optimal_k(features_scaled)

    # Train K-Means
    self.clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    self.clusterer.fit(features_scaled)

    return self.clusterer

def _find_optimal_k(self, features, max_k=10):
    """Find optimal number of clusters using elbow method."""

    from sklearn.metrics import silhouette_score

    silhouette_scores = []
    k_range = range(2, min(max_k, len(features) // 2))

    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42)
        labels = kmeans.fit_predict(features)
        score = silhouette_score(features, labels)
        silhouette_scores.append(score)

    # Return k with highest silhouette score
    optimal_k = k_range[np.argmax(silhouette_scores)]
    return optimal_k
```

### Supervised Classification (When Sample Labels Available)

```python
def train_random_forest_classifier(self, database: TopographyDatabase):
    """Train Random Forest using sample labels."""

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    # Get data with labels
    images, sample_labels = database.export_for_training()

    # Extract features
    features = np.array([self.extract_features(img) for img in images])

    # Scale
    features_scaled = self.scaler.fit_transform(features)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        features_scaled, sample_labels, test_size=0.2, random_state=42,
        stratify=sample_labels
    )

    # Train
    self.classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    self.classifier.fit(X_train, y_train)

    # Evaluate
    train_score = self.classifier.score(X_train, y_train)
    test_score = self.classifier.score(X_test, y_test)

    logger.info(f"Classifier trained: Train acc={train_score:.3f}, Test acc={test_score:.3f}")

    return {
        'train_accuracy': train_score,
        'test_accuracy': test_score,
        'n_samples': len(images),
        'n_features': features.shape[1]
    }
```

## 🎨 UI Integration

### New Tab: "ML Database" or "Sample Manager"

```python
def create_ml_database_tab(self) -> QWidget:
    """Create sample/topography database management tab."""

    widget = QWidget()
    layout = QVBoxLayout(widget)

    # === Sample Management ===
    sample_group = QGroupBox("📁 Sample Management")
    sample_layout = QVBoxLayout()

    # Sample selector
    selector_layout = QHBoxLayout()
    selector_layout.addWidget(QLabel("Current Sample:"))
    self.sample_combo = QComboBox()
    self.sample_combo.currentTextChanged.connect(self.on_sample_changed)
    selector_layout.addWidget(self.sample_combo)

    self.add_sample_btn = QPushButton("➕ Add New Sample")
    self.add_sample_btn.clicked.connect(self.add_new_sample)
    selector_layout.addWidget(self.add_sample_btn)

    sample_layout.addLayout(selector_layout)

    # Sample info
    self.sample_info_text = QTextEdit()
    self.sample_info_text.setReadOnly(True)
    self.sample_info_text.setMaximumHeight(100)
    sample_layout.addWidget(self.sample_info_text)

    sample_group.setLayout(sample_layout)
    layout.addWidget(sample_group)

    # === Image Import ===
    import_group = QGroupBox("📥 Import Topographies")
    import_layout = QVBoxLayout()

    self.import_topo_btn = QPushButton("📁 Import Topography File(s)")
    self.import_topo_btn.clicked.connect(self.import_topographies)
    import_layout.addWidget(self.import_topo_btn)

    self.import_batch_btn = QPushButton("📂 Import Folder of .nid Files")
    self.import_batch_btn.clicked.connect(self.import_topographies_batch)
    import_layout.addWidget(self.import_batch_btn)

    import_group.setLayout(import_layout)
    layout.addWidget(import_group)

    # === Database Statistics ===
    stats_group = QGroupBox("📊 Database Statistics")
    stats_layout = QVBoxLayout()

    self.db_stats_table = QTableWidget()
    self.db_stats_table.setColumnCount(3)
    self.db_stats_table.setHorizontalHeaderLabels(["Sample", "Images", "Status"])
    stats_layout.addWidget(self.db_stats_table)

    self.refresh_stats_btn = QPushButton("🔄 Refresh Statistics")
    self.refresh_stats_btn.clicked.connect(self.refresh_database_stats)
    stats_layout.addWidget(self.refresh_stats_btn)

    stats_group.setLayout(stats_layout)
    layout.addWidget(stats_group)

    # === ML Training ===
    ml_group = QGroupBox("🤖 ML Training & Analysis")
    ml_layout = QVBoxLayout()

    self.training_status_label = QLabel("Status: Not enough data for training")
    self.training_status_label.setStyleSheet("color: #cc0000; font-weight: bold;")
    ml_layout.addWidget(self.training_status_label)

    training_settings_layout = QHBoxLayout()
    training_settings_layout.addWidget(QLabel("Method:"))
    self.clustering_method_combo = QComboBox()
    self.clustering_method_combo.addItems(["K-Means", "DBSCAN", "Hierarchical", "Random Forest (Supervised)"])
    training_settings_layout.addWidget(self.clustering_method_combo)
    ml_layout.addLayout(training_settings_layout)

    self.train_model_btn = QPushButton("🎓 Train Model")
    self.train_model_btn.clicked.connect(self.train_clustering_model)
    self.train_model_btn.setEnabled(False)
    ml_layout.addWidget(self.train_model_btn)

    self.classify_current_btn = QPushButton("🔍 Classify Current Topography")
    self.classify_current_btn.clicked.connect(self.classify_current_topography)
    self.classify_current_btn.setEnabled(False)
    ml_layout.addWidget(self.classify_current_btn)

    ml_group.setLayout(ml_layout)
    layout.addWidget(ml_group)

    layout.addStretch()

    return widget
```

### Implementation Methods

```python
def add_new_sample(self):
    """Dialog to add a new sample to database."""

    from PySide6.QtWidgets import QInputDialog, QLineEdit

    sample_name, ok = QInputDialog.getText(
        self, "New Sample", "Enter sample name:",
        QLineEdit.Normal, ""
    )

    if ok and sample_name:
        description, ok = QInputDialog.getMultiLineText(
            self, "Sample Description",
            "Enter description (optional):"
        )

        try:
            self.topo_database.add_sample(sample_name, description or "")
            self.sample_combo.addItem(sample_name)
            self.sample_combo.setCurrentText(sample_name)

            QMessageBox.information(
                self, "Success",
                f"Sample '{sample_name}' added to database."
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to add sample:\n{str(e)}"
            )

def import_topographies(self):
    """Import individual .nid files as topographies."""

    current_sample = self.sample_combo.currentText()
    if not current_sample:
        QMessageBox.warning(
            self, "No Sample Selected",
            "Please select or create a sample first."
        )
        return

    # Select files
    files, _ = QFileDialog.getOpenFileNames(
        self,
        "Select .nid Files (Topography Only)",
        "",
        "Nanosurf Files (*.nid)"
    )

    if not files:
        return

    self.show_progress("Importing topographies...")

    imported = 0
    failed = 0

    for filepath in files:
        try:
            # Load .nid file
            stm_nid = nid_read(filepath)

            # Extract topography only
            if hasattr(stm_nid.data, 'Image'):
                z_forward = np.array(stm_nid.data.Image.Forward.get("Z-Axis",
                                                                   stm_nid.data.Image.Forward.get("Height")))
                z_backward = np.array(stm_nid.data.Image.Backward.get("Z-Axis",
                                                                     stm_nid.data.Image.Backward.get("Height")))

                topo_data = TopographyData.from_forward_backward(
                    z_forward, z_backward, flip_vertical=True
                )

                # Extract metadata
                metadata = {
                    'source_file': filepath,
                    'dimensions': topo_data.shape,
                    'import_date': pd.Timestamp.now().isoformat()
                }

                # Add to database
                self.topo_database.add_topography(
                    current_sample,
                    topo_data,
                    metadata,
                    Path(filepath)
                )

                imported += 1
            else:
                failed += 1
                logger.warning(f"No topography in {filepath}")

        except Exception as e:
            failed += 1
            logger.error(f"Failed to import {filepath}: {e}")

    self.hide_progress()
    self.refresh_database_stats()

    QMessageBox.information(
        self, "Import Complete",
        f"Imported: {imported} topographies\n"
        f"Failed: {failed} files"
    )

def import_topographies_batch(self):
    """Import all .nid files from a folder."""

    current_sample = self.sample_combo.currentText()
    if not current_sample:
        QMessageBox.warning(
            self, "No Sample Selected",
            "Please select or create a sample first."
        )
        return

    folder = QFileDialog.getExistingDirectory(
        self, "Select Folder with .nid Files"
    )

    if not folder:
        return

    # Find all .nid files
    nid_files = list(Path(folder).glob("*.nid"))

    if not nid_files:
        QMessageBox.warning(self, "No Files", "No .nid files found in folder.")
        return

    # Batch import (reuse import_topographies logic)
    # ... similar to above but with nid_files list

def refresh_database_stats(self):
    """Refresh the database statistics table."""

    stats = self.topo_database.get_sample_statistics()

    self.db_stats_table.setRowCount(len(stats))

    for i, row in stats.iterrows():
        self.db_stats_table.setItem(i, 0, QTableWidgetItem(row['sample_name']))
        self.db_stats_table.setItem(i, 1, QTableWidgetItem(str(row['image_count'])))

        # Status
        if row['image_count'] >= 10:
            status = "✅ Ready"
            status_color = "#00aa00"
        elif row['image_count'] >= 5:
            status = "⚠️ Needs more"
            status_color = "#ff8800"
        else:
            status = "❌ Too few"
            status_color = "#cc0000"

        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(status_color))
        self.db_stats_table.setItem(i, 2, status_item)

    # Check if training is possible
    if self.topo_database.is_training_ready():
        self.training_status_label.setText("Status: ✅ Ready for training!")
        self.training_status_label.setStyleSheet("color: #00aa00; font-weight: bold;")
        self.train_model_btn.setEnabled(True)
    else:
        total_images = stats['image_count'].sum()
        self.training_status_label.setText(
            f"Status: Need more data ({total_images} images, need 30+ across 3+ samples)"
        )
        self.training_status_label.setStyleSheet("color: #cc0000; font-weight: bold;")
        self.train_model_btn.setEnabled(False)

def train_clustering_model(self):
    """Train the clustering/classification model."""

    method = self.clustering_method_combo.currentText()

    self.show_progress("Training model...")

    try:
        self.topo_clusterer = TopographyClusterer()

        if "Random Forest" in method:
            # Supervised
            results = self.topo_clusterer.train_classifier(self.topo_database)
            msg = (f"Random Forest Classifier Trained\n\n"
                  f"Training Accuracy: {results['train_accuracy']*100:.1f}%\n"
                  f"Test Accuracy: {results['test_accuracy']*100:.1f}%\n"
                  f"Samples: {results['n_samples']}")
        else:
            # Unsupervised clustering
            images, _ = self.topo_database.export_for_training()

            if "K-Means" in method:
                self.topo_clusterer.train_clustering_kmeans(images)
                n_clusters = self.topo_clusterer.clusterer.n_clusters
                msg = f"K-Means Clustering Trained\n\nClusters: {n_clusters}"
            # ... other methods

        self.hide_progress()

        QMessageBox.information(self, "Training Complete", msg)
        self.classify_current_btn.setEnabled(True)

    except Exception as e:
        self.hide_progress()
        QMessageBox.critical(self, "Training Failed", str(e))

def classify_current_topography(self):
    """Classify the currently loaded topography."""

    if self.topography_data is None:
        QMessageBox.warning(self, "No Data", "Load topography data first.")
        return

    try:
        prediction = self.topo_clusterer.predict(self.topography_data)

        msg = f"Classification Results:\n\n"
        msg += f"Cluster: {prediction['cluster_id']}\n"
        msg += f"Confidence: {prediction['confidence']*100:.1f}%\n"
        msg += f"Similar to: {', '.join(prediction['nearest_samples'][:3])}"

        QMessageBox.information(self, "Classification", msg)

    except Exception as e:
        QMessageBox.critical(self, "Error", str(e))
```

## 💾 Data Persistence

### Database Implementation

```python
def _initialize_database(self):
    """Create database schema if not exists."""

    import sqlite3

    self.conn = sqlite3.connect(str(self.db_path))
    cursor = self.conn.cursor()

    # Create tables (schema defined earlier)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topographies (
            topo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id INTEGER NOT NULL,
            source_file TEXT,
            import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_data BLOB,
            width INTEGER,
            height INTEGER,
            physical_width_nm REAL,
            physical_height_nm REAL,
            metadata TEXT,
            features BLOB,
            FOREIGN KEY (sample_id) REFERENCES samples(sample_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sample ON topographies(sample_id)')

    self.conn.commit()

def add_topography(self, sample_name, topo_data, metadata, source_file):
    """Add topography to database."""

    import pickle

    cursor = self.conn.cursor()

    # Get sample_id
    cursor.execute('SELECT sample_id FROM samples WHERE sample_name = ?', (sample_name,))
    result = cursor.fetchone()

    if not result:
        raise ValueError(f"Sample '{sample_name}' not found")

    sample_id = result[0]

    # Serialize image data
    image_blob = pickle.dumps(topo_data.data)

    # Serialize metadata
    metadata_json = json.dumps(metadata)

    # Insert
    cursor.execute('''
        INSERT INTO topographies (
            sample_id, source_file, image_data, width, height,
            physical_width_nm, physical_height_nm, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        sample_id,
        str(source_file),
        image_blob,
        topo_data.shape[1],
        topo_data.shape[0],
        topo_data.width,
        topo_data.height,
        metadata_json
    ))

    # Update image count
    cursor.execute('''
        UPDATE samples
        SET image_count = (
            SELECT COUNT(*) FROM topographies WHERE sample_id = ?
        )
        WHERE sample_id = ?
    ''', (sample_id, sample_id))

    self.conn.commit()
    logger.info(f"Added topography to sample '{sample_name}'")
```

## 📦 Dependencies

Add to `requirements.txt`:
```
scikit-learn>=1.3.0
scikit-image>=0.20.0
tensorflow>=2.13.0  # Optional, for CNN features
opencv-python>=4.8.0  # Optional, for advanced image processing
```

---

# 🏛️ Overall Architecture

## Directory Structure

```
src/
├── ml/
│   ├── __init__.py
│   ├── peak_detector.py          # Feature 1
│   ├── outlier_detector.py       # Feature 2
│   ├── topography_database.py    # Feature 3
│   └── topography_clusterer.py   # Feature 3
├── ui/
│   └── main_window.py            # Updated with ML tabs/controls
└── ...existing modules...
```

## Workflow Integration

```
User Workflow with ML:
1. Load .nid files → Outlier Detection (Feature 2)
2. Set grid dimensions
3. Calculate derivatives
4. Auto-detect peaks (Feature 1) → Auto-generate maps
5. Import topography to database (Feature 3)
6. [After collecting data] Train clustering model
7. Classify new samples automatically
```

---

# 📈 Implementation Phases

## Phase 1: Peak Detection (Highest Priority)
**Time:** 2-3 sessions
**Dependencies:** scipy, scikit-learn
**Impact:** Immediate automation of manual process

1. Implement `PeakDetector` class
2. Scipy-based peak detection
3. Global peak clustering (DBSCAN)
4. Integration with `MapGenerator`
5. UI controls and visualization
6. Testing with real data

## Phase 2: Outlier Detection (Medium Priority)
**Time:** 1-2 sessions
**Dependencies:** scikit-learn
**Impact:** Data quality improvement

1. Implement `OutlierDetector` class
2. Feature extraction methods
3. Isolation Forest implementation
4. UI integration
5. Visualization (PCA, heatmaps)
6. Testing and validation

## Phase 3: Topography Database (Lower Priority, Long-term)
**Time:** 3-4 sessions
**Dependencies:** sqlite3, scikit-learn, potentially tensorflow
**Impact:** Long-term capability building

1. Database schema and `TopographyDatabase` class
2. Sample management UI
3. Batch import functionality
4. Feature extraction (traditional first, CNN later)
5. Clustering implementation
6. Training UI and workflow
7. Classification and prediction
8. Testing and refinement

---

# 🎯 Success Metrics

## Feature 1: Peak Detection
- ✅ Successfully detects >90% of peaks visible by eye
- ✅ <5% false positive rate
- ✅ Generated maps match manually-created maps
- ✅ Processing time <10s for 100 spectra

## Feature 2: Outlier Detection
- ✅ Removes spurious spectra (verified by inspection)
- ✅ Improves SNR in averaged spectra
- ✅ False positive rate <2%
- ✅ Doesn't remove edge-case valid spectra

## Feature 3: Topography Clustering
- ✅ Database stores images efficiently
- ✅ Clustering achieves silhouette score >0.5
- ✅ Supervised classifier achieves >80% accuracy
- ✅ Classifications match human expert judgment

---

# 🚀 Next Steps After Planning

1. **Review this plan** - Identify any missing requirements
2. **Prioritize features** - Confirm implementation order
3. **Set up development environment** - Install ML dependencies
4. **Create test datasets** - Prepare validation data
5. **Begin Phase 1** - Implement peak detection first

---

**End of ML Implementation Plan**
