import typing

import sys

from PyQt5 import uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from evtx import PyEvtxParser
from lxml import etree


class XmlElement:
    def __init__(self, root):
        self.__children = dict()
        for child in root:
            # remove namespace
            idx = child.tag.rfind('}')
            self.__children[child.tag[idx+1:]] = XmlElement(child)
        self.__node = root

    @property
    def text(self):
        return self.__node.text

    @property
    def attrib(self):
        return self.__node.attrib

    def __getitem__(self, item):
        return self.__children[item]

class EventRecord:
    def __init__(self, record):
        self.__id = record['event_record_id']
        self.__timestamp = record['timestamp']
        self.__data = record['data']
        self.__parsed = False
        self.__attrib = dict()

    @property
    def id(self):
        return self.__id

    @property
    def timestamp(self):
        return self.__timestamp

    @property
    def data(self):
        return self.__data

    @property
    def EventID(self):
        self.__parse_data()
        return self.__attrib["EventID"]

    @property
    def Provider(self):
        self.__parse_data()
        return self.__attrib["Provider"]

    @property
    def Level(self):
        levels = {
            0: "LogAlways",
            1: "Critical",
            2: "Error",
            3: "Warning",
            4: "Informational",
            5: "Verbose"
        }
        self.__parse_data()
        level_id = int(self.__attrib["Level"])
        return levels[level_id]

    def __parse_data(self):
        if self.__parsed:
            return
        # remove processing instruction
        idx = self.__data.find("?>")
        if idx != -1:
            self.__data = self.__data[idx+2:]
        root = XmlElement(etree.XML(self.__data))

        self.__attrib["EventID"] = root["System"]["EventID"].text
        self.__attrib["Level"] = root["System"]["Level"].text
        self.__attrib["Provider"] = root["System"]["Provider"].attrib["Name"]



class EvtxViewModel(QAbstractItemModel):
    def __init__(self, filename):
        super(QAbstractItemModel, self).__init__()
        self.__filename = filename
        self.__chunks = 0
        self.__columns = [
            ('TimeCreated', lambda r: r.timestamp),
            ('Provider', lambda r: r.Provider),
            ('EventID', lambda r: r.EventID),
            ('EventData', lambda r: r.Level)
        ]

        for idx in range(0, len(self.__columns)):
            self.setHeaderData(idx, Qt.Horizontal, self.__columns[0][0], Qt.DisplayRole)

        self.__records = dict()
        self.__record_ids = list()
        self.load_data()

    def load_data(self):
        self.__parser = PyEvtxParser(self.__filename)
        for record in self.__parser.records():
            self.__records[record["event_record_id"]] = EventRecord(record)
            self.__record_ids.append(record["event_record_id"])
        self.__record_ids.sort()

    def rowCount(self, parent):
        return len(self.__record_ids)

    def columnCount(self, parent):
        return len(self.__columns)

    def index(self, row: int, column: int, parent: QModelIndex = ...) -> QModelIndex:
        return self.createIndex(row, column)

    def data(self, index: QModelIndex, role: int = ...) -> typing.Any:
        if role == Qt.DisplayRole:
            row = index.row()
            record_id = self.__record_ids[row]
            record = self.__records[record_id]
            column = self.__columns[index.column()]
            return column[1](record)
        else:
            return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        return Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

    def parent(self, qmodelindex=None):
        return QModelIndex()


class EvtxView(QTableView):
    def __init__(self, filename):
        super(QTableView, self).__init__()
        self.setModel(EvtxViewModel(filename))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().hide()
        self.setShowGrid(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        uic.loadUi("layout.ui", self)

        action = self.findChild(QAction, "actionExit")
        action.triggered.connect(self.action_exit)

        action = self.findChild(QAction, "actionOpen")
        action.triggered.connect(self.action_open)

        self.__tab_widget = self.findChild(QTabWidget, "tabWidget")
        self.__tab_widget.removeTab(0)
        self.__tab_widget.removeTab(0)
        self.__tab_widget.tabCloseRequested.connect(lambda idx: self.close_tab(idx))

        self.__files = dict()

    def open_file(self, filename: str):
        index = -1
        if filename in self.__files.keys():
            index = self.__files[filename]
        else:
            new_tab = QWidget()
            index = self.__tab_widget.addTab(new_tab, filename)
            layout = QVBoxLayout()
            layout.addWidget(EvtxView(filename))
            new_tab.setLayout(layout)
            self.__files[filename] = index

        assert index != -1
        self.__tab_widget.setCurrentIndex(index)

    def close_tab(self, index):
        self.__tab_widget.removeTab(index)
        tmp = dict()
        for filename, idx in self.__files.items():
            if idx != index:
                tmp[filename] = self.__files[filename]
        self.__files = tmp

    def action_exit(self):
        self.close()

    def action_open(self):
        dlg = QFileDialog()
        dlg.setAcceptMode(QFileDialog.AcceptOpen)
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter("Windows event log files (*.evtx)")
        filenames = list()
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            assert len(filenames) == 1
            self.open_file(filenames[0])


def run_app():
    app = QApplication([])

    wnd_main = MainWindow()
    wnd_main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    run_app()
