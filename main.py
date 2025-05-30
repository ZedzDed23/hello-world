import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QTreeView,
    QListView, # This will be renamed to self.file_list_view
    QLineEdit,
    QToolBar,
    QStatusBar,
    QFileSystemModel,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QDir, QFileInfo, Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("File Manager")

        # Address bar
        self.address_bar = QLineEdit()

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        # Toolbar actions
        self.back_action = QAction(QIcon.fromTheme("go-previous"), "Back", self)
        self.forward_action = QAction(QIcon.fromTheme("go-next"), "Forward", self)
        self.up_action = QAction(QIcon.fromTheme("go-up"), "Up", self) # Stored as self.up_action

        self.toolbar.addAction(self.back_action)
        self.toolbar.addAction(self.forward_action)
        self.toolbar.addAction(self.up_action)

        # Directory tree and file/folder list
        self.tree_view = QTreeView()
        self.file_list_view = QListView() # Renamed from self.list_view

        # Filesystem Model for the list view
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.rootPath()) # Set root to allow navigation anywhere
        self.fs_model.setFilter(QDir.AllEntries | QDir.Hidden) # Show all entries including hidden, no dot/dotdot
        self.fs_model.setNameSortingEnabled(True) # Enables model-level sorting capability
        
        self.file_list_view.setModel(self.fs_model)
        # Initial directory is set via change_directory later

        # Configure the Tree View
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(QDir.rootPath()))
        self.tree_view.hideColumn(1)  # Size
        self.tree_view.hideColumn(2)  # Type
        self.tree_view.hideColumn(3)  # Date Modified
        self.tree_view.setHeaderHidden(True) # Optional: hide header
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)


        # Sort by name initially for the model (affects both views if they don't override)
        # It's often better to set sorting on the view if views need different sort orders.
        # QFileSystemModel sorts itself if setNameSortingEnabled is true.
        # self.fs_model.sort(0, Qt.AscendingOrder) # Already enabled by setNameSortingEnabled for column 0

        # Splitter
        splitter = QSplitter()
        splitter.addWidget(self.tree_view)
        splitter.addWidget(self.file_list_view)

        # Central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.address_bar)
        layout.addWidget(splitter)

        self.setCentralWidget(central_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # History
        self.history = []
        self.history_position = -1

        # Initialize directory and address bar (this will populate history)
        self.change_directory(QDir.homePath()) # is_history_navigation defaults to False

        # Connect signals
        self.back_action.triggered.connect(self.go_back)
        self.forward_action.triggered.connect(self.go_forward)
        self.file_list_view.doubleClicked.connect(self.on_list_view_double_clicked)
        self.address_bar.returnPressed.connect(self.on_address_bar_return_pressed)
        self.up_action.triggered.connect(self.go_up)
        self.tree_view.clicked.connect(self.on_tree_view_clicked)

        # Set initial state for history buttons
        self.update_history_buttons_state()


    def change_directory(self, path_string, is_history_navigation=False):
        """
        Changes the current directory in the file list view and updates the address bar.
        Manages navigation history.
        is_history_navigation: True if called from back/forward, False otherwise.
        """
        # Use QDir for robust path handling and normalization
        target_dir = QDir(path_string)
        
        if not target_dir.exists():
            self.status_bar.showMessage(f"Path does not exist: {path_string}", 5000)
            # Revert address bar if the input was from there
            if not is_history_navigation: # Avoid reverting if history navigation led to an invalid path (should be rare)
                current_path = self.fs_model.filePath(self.file_list_view.rootIndex())
                self.address_bar.setText(current_path)
            return

        normalized_path = target_dir.absolutePath() # Canonical and absolute

        # Avoid doing anything if navigating to the same path currently shown
        current_shown_path_index = self.file_list_view.rootIndex()
        if current_shown_path_index.isValid() and self.fs_model.filePath(current_shown_path_index) == normalized_path:
            # If it's not history navigation, ensure buttons are updated (e.g. if user types same path)
            if not is_history_navigation:
                 self.update_history_buttons_state() # In case history was cleared then same path re-entered
            return

        model_index = self.fs_model.index(normalized_path)

        if model_index.isValid() and self.fs_model.isDir(model_index):
            # Actual directory change happens here
            self.file_list_view.setRootIndex(model_index)
            self.address_bar.setText(normalized_path)

            if not is_history_navigation:
                # If we are at a point in history and navigate to a new path,
                # truncate the "future" part of the history.
                if self.history_position < len(self.history) - 1:
                    self.history = self.history[:self.history_position + 1]
                
                # Add to history only if it's different from the current last entry
                if not self.history or self.history[-1] != normalized_path:
                    self.history.append(normalized_path)
                self.history_position = len(self.history) - 1
            
            self.update_history_buttons_state()
        
        elif not self.fs_model.isDir(model_index) and model_index.isValid():
            self.status_bar.showMessage(f"Not a directory: {normalized_path}", 3000)
            if not is_history_navigation:
                current_path = self.fs_model.filePath(self.file_list_view.rootIndex())
                self.address_bar.setText(current_path)
        else:
            self.status_bar.showMessage(f"Cannot navigate to: {normalized_path}", 3000)
            if not is_history_navigation:
                current_path = self.fs_model.filePath(self.file_list_view.rootIndex())
                self.address_bar.setText(current_path)


    def on_list_view_double_clicked(self, index):
        """
        Handles double-click events on the file list view.
        If a directory is clicked, navigates into it.
        """
        if self.fs_model.isDir(index):
            path = self.fs_model.filePath(index)
            self.change_directory(path, is_history_navigation=False)

    def on_address_bar_return_pressed(self):
        """
        Handles return key press in the address bar to navigate to the entered path.
        """
        path = self.address_bar.text()
        self.change_directory(path, is_history_navigation=False)

    def go_up(self):
        """
        Navigates to the parent directory.
        """
        current_root_index = self.file_list_view.rootIndex()
        current_path = self.fs_model.filePath(current_root_index)
        
        # Using QDir to navigate up guarantees canonical path handling (e.g. / -> /)
        parent_dir = QDir(current_path)
        if parent_dir.cdUp():
            self.change_directory(parent_dir.absolutePath(), is_history_navigation=False)
        else:
            # This might happen if already at root or due to permissions
            self.status_bar.showMessage(f"Cannot go up from: {current_path}", 3000)

    def go_back(self):
        if self.history_position > 0:
            self.history_position -= 1
            path_to_go = self.history[self.history_position]
            self.change_directory(path_to_go, is_history_navigation=True)

    def go_forward(self):
        if self.history_position < len(self.history) - 1:
            self.history_position += 1
            path_to_go = self.history[self.history_position]
            self.change_directory(path_to_go, is_history_navigation=True)

    def update_history_buttons_state(self):
        self.back_action.setEnabled(self.history_position > 0)
        self.forward_action.setEnabled(self.history_position < len(self.history) - 1)

    def on_tree_view_clicked(self, index):
        """
        Handles click events on the tree view.
        If a directory is clicked, navigates the file list view and address bar to it.
        """
        path_string = self.fs_model.filePath(index)
        if self.fs_model.isDir(index):
            self.change_directory(path_string, is_history_navigation=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
