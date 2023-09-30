import sys
import os
import threading
from PySide2.QtCore import Qt, QUrl, QTime, QObject, Signal
from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QFileDialog, QProgressBar, QStyleFactory
from PySide2.QtMultimedia import QMediaPlayer, QMediaContent
from PySide2.QtMultimediaWidgets import QVideoWidget
from spleeter.separator import Separator
from pydub import AudioSegment


class Worker(QObject):
    progress = Signal(int)
    song_separated = Signal(str)
    song_metadata = Signal(str)
    finished = Signal()
    adjust_stem_sound = Signal(list)

    def __init__(self, song_path, output_dir, num_stems):
        super().__init__()
        self.song_path = song_path
        self.output_dir = output_dir
        self.num_stems = num_stems
        self.gain_values = [0.0] * self.num_stems

    def run(self):
        self.progress.emit(0)

        separator = Separator('spleeter:{:d}stems'.format(self.num_stems))
        separator.separate_to_file(self.song_path, self.output_dir)

        self.progress.emit(100)
        self.song_separated.emit("Separation complete.")

        song_metadata = self.get_song_metadata()
        self.song_metadata.emit(song_metadata)

        self.finished.emit()

    def get_song_metadata(self):
        audio = AudioSegment.from_file(self.song_path)
        duration = len(audio) / 1000.0
        channels = audio.channels
        sample_width = audio.sample_width
        frame_rate = audio.frame_rate

        metadata = f"Duration: {duration:.2f} seconds\n"
        metadata += f"Channels: {channels}\n"
        metadata += f"Sample Width: {sample_width} bytes\n"
        metadata += f"Frame Rate: {frame_rate} Hz"

        return metadata

    def set_gain_values(self, gain_values):
        self.gain_values = gain_values
        self.adjust_stem_sound.emit(self.gain_values)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.song_path = ''
        self.video_path = ''
        self.stems = 2
        self.separator = None
        self.player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.progress_bar = QProgressBar()
        self.player = QMediaPlayer()

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Spleeter Player")
        self.setGeometry(200, 200, 400, 400)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.file_label = QLabel("No file selected.")
        self.layout.addWidget(self.file_label)

        self.file_button = QPushButton("Select Audio File")
        self.file_button.clicked.connect(self.select_audio_file)
        self.layout.addWidget(self.file_button)

        self.video_button = QPushButton("Select Video File")
        self.video_button.clicked.connect(self.select_video_file)
        self.layout.addWidget(self.video_button)

        self.stems_label = QLabel("Number of Stems:")
        self.layout.addWidget(self.stems_label)

        self.stems_button_layout = QHBoxLayout()

        self.stems_2_button = QPushButton("2 Stems")
        self.stems_2_button.clicked.connect(lambda: self.change_stems(2))
        self.stems_button_layout.addWidget(self.stems_2_button)

        self.stems_4_button = QPushButton("4 Stems")
        self.stems_4_button.clicked.connect(lambda: self.change_stems(4))
        self.stems_button_layout.addWidget(self.stems_4_button)

        self.stems_5_button = QPushButton("5 Stems")
        self.stems_5_button.clicked.connect(lambda: self.change_stems(5))
        self.stems_button_layout.addWidget(self.stems_5_button)

        self.layout.addLayout(self.stems_button_layout)

        self.sliders_layout = QVBoxLayout()
        self.sliders = []
        self.gain_values = []

        self.separator_button = QPushButton("Separate")
        self.separator_button.clicked.connect(self.separate_song)
        self.layout.addWidget(self.separator_button)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_song)
        self.layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_song)
        self.layout.addWidget(self.stop_button)

        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.layout.addWidget(self.progress_bar)

        self.player.positionChanged.connect(self.update_position)

        self.layout.addWidget(self.video_widget)

        self.player.setVideoOutput(self.video_widget)

        self.setAcceptDrops(True)

    def select_audio_file(self):
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Audio Files (*.mp3 *.wav)")
        if file_dialog.exec_():
            self.song_path = file_dialog.selectedFiles()[0]
            self.file_label.setText(self.song_path)

    def select_video_file(self):
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Video Files (*.mp4)")
        if file_dialog.exec_():
            self.video_path = file_dialog.selectedFiles()[0]
            self.load_video()

    def change_stems(self, num_stems):
        self.stems = num_stems
        self.remove_sliders()
        self.create_sliders()

        stem_names = {
            2: ["Vocals (singing voice)", "Accompaniment"],
            4: ["Vocals", "Drums", "Bass", "Other"],
            5: ["Vocals", "Drums", "Bass", "Piano", "Other"],
        }

        if self.stems in stem_names:
            names = stem_names[self.stems]
            stems_text = ", ".join(names)
            self.stems_label.setText(
                f"Number of Stems: {self.stems} ({stems_text})")

    def create_sliders(self):
        self.gain_values = [0.0] * self.stems

        stem_names = {
            2: ["Vocals (singing voice)", "Accompaniment"],
            4: ["Vocals", "Drums", "Bass", "Other"],
            5: ["Vocals", "Drums", "Bass", "Piano", "Other"],
        }

        self.remove_sliders()

        self.sliders_layout = QVBoxLayout()
        self.sliders = []

        if self.stems in stem_names:
            names = stem_names[self.stems]

            for name in names:
                label = QLabel(name)
                slider = QSlider(Qt.Horizontal)
                slider.setMinimum(-100)
                slider.setMaximum(100)
                slider.setValue(0)
                # Capture the index as a default argument
                idx = names.index(name)
                slider.valueChanged.connect(
                    lambda value, idx=idx: self.slider_moved(value, idx))
                slider.valueChanged.connect(
                    lambda value, idx=idx: self.adjust_stem_audio(self.gain_values))

                self.sliders_layout.addWidget(label)
                self.sliders_layout.addWidget(slider)

                self.sliders.append(slider)

            self.layout.addLayout(self.sliders_layout)

    def remove_sliders(self):
        for slider in self.sliders:
            slider.setParent(None)
            slider.deleteLater()
        self.sliders = []

        # Remove the slider labels
        while self.sliders_layout.count():
            item = self.sliders_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            else:
                layout = item.layout()
                if layout:
                    while layout.count():
                        item = layout.takeAt(0)
                        widget = item.widget()
                        if widget:
                            widget.setParent(None)
        self.sliders_layout.setParent(None)

    def slider_moved(self, value, index):
        self.gain_values[index] = value / 100.0
        self.worker.adjust_stem_sound.emit(self.gain_values)

    def separate_song(self):
        if self.song_path:
            output_dir = os.path.dirname(self.song_path)
            self.progress_bar.setValue(0)
            self.file_label.setText("Separating...")
            self.separator_button.setEnabled(False)
            self.worker = Worker(self.song_path, output_dir, self.stems)
            self.worker.progress.connect(self.update_progress)
            self.worker.song_separated.connect(self.song_separated)
            self.worker.song_metadata.connect(self.update_song_metadata)
            self.worker.finished.connect(self.separation_complete)
            self.worker.adjust_stem_sound.connect(self.adjust_stem_audio)
            self.thread = threading.Thread(target=self.worker.run)
            self.thread.start()

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def song_separated(self, message):
        self.file_label.setText(message)

    def update_song_metadata(self, metadata):
        self.setWindowTitle(f"Spleeter Player - {metadata}")

    def separation_complete(self):
        self.separator_button.setEnabled(True)

    def play_song(self):
        if self.song_path:
            self.player.stop()

            audio = AudioSegment.from_file(self.song_path)

            # Create a list to store the adjusted audio segments for each stem
            adjusted_audio_segments = []

            for i, slider in enumerate(self.sliders):
                gain_value = self.gain_values[i]
                channel_index = i % 2  # Alternating between 0 and 1 for stereo channels
                adjusted_audio = audio.split_to_mono(
                )[channel_index].apply_gain(gain_value)
                adjusted_audio_segments.append(adjusted_audio)

            # Combine the adjusted audio segments into a single audio segment
            combined_audio = sum(adjusted_audio_segments)

            # Specify a temporary audio filename
            temp_audio_filename = "temp_audio.wav"

            # Export the combined audio to the temporary file
            combined_audio.export(temp_audio_filename, format="wav")

            try:
                # Set the media content of the player to the temporary audio file
                self.player.setMedia(QMediaContent(
                    QUrl.fromLocalFile(temp_audio_filename)))

                # Start playing the song
                self.player.play()
            except Exception as e:
                # Handle any exceptions that may occur during playback
                print(f"Error during playback: {e}")

    def adjust_stem_audio(self, gain_values):
        if self.song_path:
            audio = AudioSegment.from_file(self.song_path)

            # Create a list to store the adjusted audio segments for each stem
            adjusted_audio_segments = []

            for i, gain_value in enumerate(gain_values):
                if i == 0:
                    adjusted_audio = audio.split_to_mono()[
                        0].apply_gain(gain_value)
                else:
                    adjusted_audio = audio.split_to_mono()[
                        1].apply_gain(gain_value)
                adjusted_audio_segments.append(adjusted_audio)

            # Combine the adjusted audio segments into a single audio segment
            combined_audio = sum(adjusted_audio_segments)

            # Export the combined audio to a temporary file
            combined_audio.export("temp_audio.wav", format="wav")

            # Set the media content of the player to the temporary audio file
            self.player.setMedia(QMediaContent(
                QUrl.fromLocalFile("temp_audio.wav")))

    def stop_song(self):
        self.player.stop()

    def update_position(self, position):
        self.progress_bar.setValue(position)

    def load_video(self):
        if self.video_path:
            self.player.setMedia(QMediaContent(
                QUrl.fromLocalFile(self.video_path)))
            self.player.setVideoOutput(self.video_widget)
            self.video_widget.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
