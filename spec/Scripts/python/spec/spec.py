import re
import threading
import tempfile
import uno
import common
import config
import textwidth


class SpecBuildingThread(threading.Thread):
    """Спецификация заполняется из отдельного вычислительного потока.

    Из-за особенностей реализации uno-интерфейса, процесс построения специф.
    занимает значительное время. Чтобы избежать продолжительного зависания
    графического интерфейса LibreOffice, специф. заполняется из отдельного
    вычислительного потока и внесённые изменения сразу же отображаются в окне
    текстового редактора.

    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = "SpecBuildingThread"

    def run(self):
        schematic = common.getSchematicData()
        if schematic is None:
            return
        clean(force=True)
        doc = XSCRIPTCONTEXT.getDocument()
        table = doc.getTextTables().getByName("Спецификация")
        compGroups = schematic.getGroupedComponents()
        prevGroup = None
        emptyRowsType = config.getint("spec", "empty rows between diff type")
        lastRow = table.getRows().getCount() - 1
        # В процессе заполнения специф., в конце таблицы всегда должна
        # оставаться пустая строка с ненарушенным форматированием.
        # На её основе будут создаваться новые строки.
        # По окончанию, последняя строка будет удалена.
        table.getRows().insertByIndex(lastRow, 1)

        def nextRow():
            nonlocal lastRow
            lastRow += 1
            table.getRows().insertByIndex(lastRow, 1)

        def fillSectionTitle(section):
            doc.lockControllers()
            cell = table.getCellByPosition(4, lastRow)
            cellCursor = cell.createTextCursor()
            cellCursor.ParaStyleName = "Наименование (заголовок раздела)"
            cell.setString(section)
            nextRow()
            doc.unlockControllers()

        def fillRow(values, isTitle=False, posIncrement=0):
            colNames = (
                "Формат",
                "Зона",
                "Поз.",
                "Обозначение",
                "Наименование",
                "Кол.",
                "Примечание"
            )
            widthFactors = [100] * len(values)
            extraRow = [""] * len(values)
            extremeWidthFactor = config.getint("spec", "extreme width factor")
            for index, value in enumerate(values):
                if '\n' in value:
                    lfPos = value.find('\n')
                    values[index] = value[:lfPos]
                    extraRow[index] = value[(lfPos + 1):]
            normValues = list(values)
            for index, value in enumerate(normValues):
                widthFactors[index] = textwidth.getWidthFactor(
                    colNames[index],
                    value
                )
            # Обозначение
            if widthFactors[3] < extremeWidthFactor:
                name = values[3]
                extremePos = int(len(name) * widthFactors[3] / extremeWidthFactor)
                # Первая попытка: определить длину не превышающую критическое
                # сжатие шрифта.
                pos = name.rfind(" ", 0, extremePos)
                if pos == -1:
                    # Вторая попытка: определить длину, которая хоть и
                    # превышает критическое значение, но всё же меньше
                    # максимального.
                    pos = name.find(" ", extremePos)
                if pos != -1:
                    normValues[3] = name[:pos]
                    extraRow[3] = name[(pos + 1):] + extraRow[3]
                widthFactors[3] = textwidth.getWidthFactor(
                    colNames[3],
                    normValues[3]
                )
            # Наименование
            if widthFactors[4] < extremeWidthFactor:
                name = values[4]
                extremePos = int(len(name) * widthFactors[4] / extremeWidthFactor)
                # Первая попытка: определить длину не превышающую критическое
                # сжатие шрифта.
                pos = name.rfind(" ", 0, extremePos)
                if pos == -1:
                    # Вторая попытка: определить длину, которая хоть и
                    # превышает критическое значение, но всё же меньше
                    # максимального.
                    pos = name.find(" ", extremePos)
                if pos != -1:
                    normValues[4] = name[:pos]
                    extraRow[4] = name[(pos + 1):] + extraRow[4]
                widthFactors[4] = textwidth.getWidthFactor(
                    colNames[4],
                    normValues[4]
                )
            # Примечание
            if widthFactors[6] < extremeWidthFactor:
                comment = values[6]
                extremePos = int(len(comment) * widthFactors[6] / extremeWidthFactor)
                # Первая попытка: определить длину не превышающую критическое
                # сжатие шрифта.
                pos1 = comment.rfind(" ", 0, extremePos)
                pos2 = comment.rfind("-", 0, extremePos)
                pos = max(pos1, pos2)
                if pos == -1:
                    # Вторая попытка: определить длину, которая хоть и
                    # превышает критическое значение, но всё же меньше
                    # максимального.
                    pos1 = comment.find(" ", extremePos)
                    pos2 = comment.find("-", extremePos)
                    pos = max(pos1, pos2)
                if pos != -1:
                    separator = comment[pos]
                    if separator == " ":
                        normValues[6] = comment[:pos]
                        extraRow[6] = comment[(pos + 1):] + extraRow[6]
                    elif separator == "-":
                        normValues[6] = comment[:(pos + 1)]
                        extraRow[6] = comment[pos:] + extraRow[6]
                widthFactors[6] = textwidth.getWidthFactor(
                    colNames[6],
                    normValues[6]
                )

            doc.lockControllers()
            for i in range(len(values)):
                cell = table.getCellByPosition(i, lastRow)
                cellCursor = cell.createTextCursor()
                if isTitle and i == 4:
                    cellCursor.ParaStyleName = "Наименование (заголовок группы)"
                cellCursor.CharScaleWidth = widthFactors[i]
                if posIncrement and i == 2:
                    if doc.getTextFieldMasters().hasByName("com.sun.star.text.fieldmaster.SetExpression.Позиция"):
                        posFieldMaster = doc.getTextFieldMasters().getByName("com.sun.star.text.fieldmaster.SetExpression.Позиция")
                    else:
                        posFieldMaster = doc.createInstance("com.sun.star.text.fieldmaster.SetExpression")
                        posFieldMaster.SubType = 0
                        posFieldMaster.Name = "Позиция"
                    posField = doc.createInstance("com.sun.star.text.textfield.SetExpression")
                    posField.Content = "Позиция+" + str(posIncrement)
                    posField.attachTextFieldMaster(posFieldMaster)
                    cell.getText().insertTextContent(cellCursor, posField, False)
                else:
                    cell.setString(normValues[i])
            nextRow()
            doc.unlockControllers()

            if any(extraRow):
                fillRow(extraRow, isTitle)

        if config.getboolean("sections", "documentation"):
            if not config.getboolean("spec", "prohibit empty rows at top"):
                nextRow()
            fillSectionTitle("Документация")

            if config.getboolean("sections", "assembly") \
                or config.getboolean("sections", "schematic") \
                or config.getboolean("sections", "index"):
                    nextRow()

            if config.getboolean("sections", "assembly"):
                name = "Сборочный чертёж"
                fillRow(
                    ["", "", "", "", name, "", ""]
                )

            if config.getboolean("sections", "schematic"):
                size, ref = common.getSchematicInfo()
                name = "Схема электрическая принципиальная"
                fillRow(
                    [size, "", "", ref, name, "", ""]
                )

            if config.getboolean("sections", "index"):
                size, ref = common.getSchematicInfo()
                size = "A4"
                refParts = re.match(
                    r"([А-ЯA-Z0-9]+(?:[\.\-]\d+)+\s?)(Э\d)",
                    ref
                )
                if refParts is not None:
                    ref = 'П'.join(refParts.groups())
                name = "Перечень элементов"
                fillRow(
                    [size, "", "", ref, name, "", ""]
                )

        if config.getboolean("sections", "details"):
            nextRow()
            fillSectionTitle("Детали")

            if config.getboolean("sections", "pcb"):
                nextRow()
                size, ref = common.getPcbInfo()
                name = "Плата печатная"
                fillRow(
                    [size, "", "", ref, name, "", ""],
                    posIncrement=1
                )

        if config.getboolean("sections", "standard parts"):
            nextRow()
            fillSectionTitle("Стандартные изделия")

        if config.getboolean("sections", "other parts"):
            nextRow()
            fillSectionTitle("Прочие изделия")

            nextRow()
            for group in compGroups:
                increment = 1
                if prevGroup is not None:
                    doc.lockControllers()
                    for _ in range(emptyRowsType):
                        nextRow()
                        if config.getboolean("spec", "reserve position numbers"):
                            increment += 1
                    doc.unlockControllers()
                if len(group) == 1 \
                    and not config.getboolean("spec", "every group has title"):
                        compType = group[0].getTypeSingular()
                        compName = group[0].getSpecValue("name")
                        compDoc = group[0].getSpecValue("doc")
                        name = ""
                        if compType:
                            name += compType + ' '
                        name += compName
                        if compDoc:
                            name += ' ' + compDoc
                        compRef = group[0].getRefRangeString()
                        compComment = group[0].getSpecValue("comment")
                        comment = compRef
                        if comment:
                            if compComment:
                                comment = comment + '\n' + compComment
                        else:
                            comment = compComment
                        fillRow(
                            ["", "", "", "", name, "1", comment],
                            posIncrement=increment
                        )
                        prevGroup = group
                        continue
                titleLines = group.getTitle()
                for title in titleLines:
                    fillRow(
                        ["", "", "", "", title, "", ""],
                        isTitle=True
                    )
                if config.getboolean("spec", "empty row after group title"):
                    nextRow()
                    if config.getboolean("spec", "reserve position numbers"):
                        increment += 1
                for compRange in group:
                    compName = compRange.getSpecValue("name")
                    compDoc = compRange.getSpecValue("doc")
                    name = compName
                    if compDoc:
                        for title in titleLines:
                            if title.endswith(compDoc):
                                break
                        else:
                            name += ' ' + compDoc
                    compRef = compRange.getRefRangeString()
                    compComment = compRange.getSpecValue("comment")
                    comment = compRef
                    if comment:
                        if compComment:
                            comment = comment + '\n' + compComment
                    else:
                        comment = compComment
                    fillRow(
                        ["", "", "", "", name, str(len(compRange)), comment],
                        posIncrement=increment
                    )
                    increment = 1
                prevGroup = group

        if config.getboolean("sections", "materials"):
            nextRow()
            fillSectionTitle("Материалы")
            nextRow()

        table.getRows().removeByIndex(lastRow, 2)

        if config.getboolean("spec", "prohibit titles at bottom"):
            firstPageStyleName = doc.getText().createTextCursor().PageDescName
            tableRowCount = table.getRows().getCount()
            firstRowCount = 28
            otherRowCount = 32
            if firstPageStyleName.endswith("3") \
                or firstPageStyleName.endswith("4"):
                    firstRowCount = 26
            pos = firstRowCount
            while pos < tableRowCount:
                cell = table.getCellByPosition(4, pos)
                cellCursor = cell.createTextCursor()
                if cellCursor.ParaStyleName.startswith("Наименование (заголовок") \
                    and cellCursor.getText().getString() != "":
                        offset = 1
                        while pos > offset:
                            cell = table.getCellByPosition(4, pos - offset)
                            cellCursor = cell.createTextCursor()
                            if not cellCursor.ParaStyleName.startswith("Наименование (заголовок") \
                                or cellCursor.getText().getString() == "":
                                    doc.lockControllers()
                                    table.getRows().insertByIndex(pos - offset, offset)
                                    doc.unlockControllers()
                                    break
                            offset += 1
                pos += otherRowCount

        if config.getboolean("spec", "prohibit empty rows at top"):
            firstPageStyleName = doc.getText().createTextCursor().PageDescName
            tableRowCount = table.getRows().getCount()
            firstRowCount = 29
            otherRowCount = 32
            if firstPageStyleName.endswith("3") \
                or firstPageStyleName.endswith("4"):
                    firstRowCount = 27
            pos = firstRowCount
            while pos < tableRowCount:
                doc.lockControllers()
                while True:
                    rowIsEmpty = False
                    for i in range(7):
                        cell = table.getCellByPosition(i, pos)
                        cellCursor = cell.createTextCursor()
                        if cellCursor.getText().getString() != "":
                            break
                    else:
                        rowIsEmpty = True
                    if not rowIsEmpty:
                        break
                    table.getRows().removeByIndex(pos, 1)
                pos += otherRowCount
                doc.unlockControllers()

        doc.lockControllers()
        for rowIndex in range(1, table.getRows().getCount()):
            table.getRows().getByIndex(rowIndex).Height = common.getSpecRowHeight(rowIndex)
        doc.unlockControllers()

        if config.getboolean("spec", "append rev table"):
            pageCount = XSCRIPTCONTEXT.getDesktop().getCurrentComponent().CurrentController.PageCount
            if pageCount > config.getint("spec", "pages rev table"):
                common.appendRevTable()


def clean(*args, force=False):
    """Очистить спецификацию.

    Удалить всё содержимое из таблицы спецификации, оставив только
    заголовок и одну пустую строку.

    """
    if not force and common.isThreadWorking():
        return
    doc = XSCRIPTCONTEXT.getDocument()
    doc.lockControllers()
    text = doc.getText()
    cursor = text.createTextCursor()
    firstPageStyleName = cursor.PageDescName
    text.setString("")
    cursor.ParaStyleName = "Пустой"
    cursor.PageDescName = firstPageStyleName
    # Если не оставить параграф перед таблицей, то при изменении форматирования
    # в ячейках с автоматическими стилями будет сбрасываться стиль страницы на
    # стиль по умолчанию.
    text.insertControlCharacter(
        cursor,
        uno.getConstantByName(
            "com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK"
        ),
        False
    )
    # Таблица
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(2, 7)
    text.insertTextContent(text.getEnd(), table, False)
    table.setName("Спецификация")
    table.HoriOrient = uno.getConstantByName("com.sun.star.text.HoriOrientation.LEFT_AND_WIDTH")
    table.Width = 18500
    table.LeftMargin = 2000
    columnSeparators = table.TableColumnSeparators
    columnSeparators[0].Position = 324   # int((6)/185*10000)
    columnSeparators[1].Position = 648   # int((6+6)/185*10000)
    columnSeparators[2].Position = 1081  # int((6+6+8)/185*10000)
    columnSeparators[3].Position = 4864  # int((6+6+8+70)/185*10000)
    columnSeparators[4].Position = 8270  # int((6+6+8+70+63)/185*10000)
    columnSeparators[5].Position = 8810  # int((6+6+8+70+63+10)/185*10000)
    table.TableColumnSeparators = columnSeparators
    # Обрамление
    border = table.TableBorder
    noLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine.OuterLineWidth = 50
    border.TopLine = noLine
    border.LeftLine = noLine
    border.RightLine = noLine
    border.BottomLine = normalLine
    border.HorizontalLine = normalLine
    border.VerticalLine = normalLine
    table.TableBorder = border
    # Заголовок
    table.RepeatHeadline = True
    table.HeaderRowCount = 1
    table.getRows().getByIndex(0).Height = 1500
    table.getRows().getByIndex(0).IsAutoHeight = False
    headerNames = (
        ("A1", "Формат"),
        ("B1", "Зона"),
        ("C1", "Поз."),
        ("D1", "Обозначение"),
        ("E1", "Наименование"),
        ("F1", "Кол."),
        ("G1", "Приме-\nчание")
    )
    for cellName, headerName in headerNames:
        cell = table.getCellByName(cellName)
        cellCursor = cell.createTextCursor()
        cellCursor.ParaStyleName = "Заголовок графы таблицы"
        cell.TopBorderDistance = 50
        cell.BottomBorderDistance = 50
        cell.LeftBorderDistance = 50
        cell.RightBorderDistance = 50
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
        if cellName in ("A1", "B1", "C1", "F1"):
            cellCursor.CharRotation = 900
            if cellName == "A1":
                cellCursor.CharScaleWidth = 85
            if cellName in ("A1", "B1"):
                cell.LeftBorderDistance = 0
                cell.RightBorderDistance = 100
        cell.setString(headerName)
    # Строки
    table.getRows().getByIndex(1).Height = 800
    table.getRows().getByIndex(1).IsAutoHeight = False
    cellStyles = (
        ("A2", "Формат"),
        ("B2", "Зона"),
        ("C2", "Поз."),
        ("D2", "Обозначение"),
        ("E2", "Наименование"),
        ("F2", "Кол."),
        ("G2", "Примечание")
    )
    for cellName, cellStyle in cellStyles:
        cell = table.getCellByName(cellName)
        cursor = cell.createTextCursor()
        cursor.ParaStyleName = cellStyle
        cell.TopBorderDistance = 0
        cell.BottomBorderDistance = 0
        cell.LeftBorderDistance = 50
        cell.RightBorderDistance = 50
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
    doc.unlockControllers()

def build(*args):
    """Построить спецификацию.

    Построить спецификацию на основе данных из файла списка цепей.

    """
    if common.isThreadWorking():
        return
    specBuilder = SpecBuildingThread()
    specBuilder.start()

def toggleRevTable(*args):
    """Добавить/удалить таблицу регистрации изменений"""
    if common.isThreadWorking():
        return
    doc = XSCRIPTCONTEXT.getDocument()
    config.set("spec", "append rev table", "no")
    config.save()
    if doc.getTextTables().hasByName("Лист_регистрации_изменений"):
        common.removeRevTable()
    else:
        common.appendRevTable()
