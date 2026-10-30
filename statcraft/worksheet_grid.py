"""Original compact worksheet surface with frozen headers and cell borders."""
import tkinter as tk
import math


class WorksheetGrid(tk.Canvas):
    HEADER = 42
    ROW = 22
    GUTTER = 44

    def __init__(self, master, **kwargs):
        kwargs.pop('show', None); kwargs.pop('selectmode', None)
        super().__init__(master, background='white', highlightthickness=1,
                         highlightbackground='#c7c7c7', **kwargs)
        self._columns, self._headings, self._widths = [], {}, {}
        self._rows, self._order = {}, []
        self._x = self._y = 0
        self._focused, self._selected = '', set()
        self._selection_columns = None
        self._active_column = 0
        self._pending = False
        self._paint_id = None
        self._xcommand = self._ycommand = None
        self.bind('<Configure>', lambda event: self._redraw())
        self.bind('<MouseWheel>', self._wheel)
        self.bind('<Destroy>', self._destroyed, add='+')

    def _destroyed(self,event):
        if event.widget is self and self._paint_id is not None:
            try: self.after_cancel(self._paint_id)
            except tk.TclError: pass
            self._paint_id = None

    def configure(self, cnf=None, **kwargs):
        if 'columns' in kwargs:
            self._columns = list(kwargs.pop('columns'))
        if 'yscrollcommand' in kwargs:
            self._ycommand = kwargs.pop('yscrollcommand')
        if 'xscrollcommand' in kwargs:
            self._xcommand = kwargs.pop('xscrollcommand')
        result = super().configure(cnf, **kwargs)
        if hasattr(self, '_pending'): self._redraw()
        return result

    config = configure

    def heading(self, column, **kwargs):
        self._headings[column] = kwargs.get('text', '')
        self._redraw()

    def column(self, column, **kwargs):
        if column != '#0': self._widths[column] = kwargs.get('width', 110)
        self._redraw()

    def insert(self, parent, position, iid, text='', values=()):
        iid = str(iid)
        self._rows[iid] = (str(text), list(values))
        self._order.append(iid)
        self._redraw()
        return iid

    def get_children(self): return tuple(self._order)

    def delete(self, *items):
        for iid in items:
            self._rows.pop(str(iid), None)
        self._order = [iid for iid in self._order if iid in self._rows]
        self._redraw()

    def exists(self, iid): return str(iid) in self._rows

    def selection_set(self, items):
        self._selected = {str(iid) for iid in items}
        self._redraw()

    def set_cell_selection(self, row, column, anchor, end):
        self._active_column = column
        self._selection_columns = tuple(sorted((anchor[1], end[1])))
        self._focused = str(row)
        self._redraw()

    def focus(self, iid=None):
        if iid is not None:
            self._focused = str(iid); self._redraw()
        return self._focused

    def identify_row(self, y):
        if y < self.HEADER: return ''
        index = int((y-self.HEADER+self._y)//self.ROW)
        return self._order[index] if 0 <= index < len(self._order) else ''

    def identify_column(self, x):
        if x < self.GUTTER: return '#0'
        value = x-self.GUTTER+self._x
        for index, column in enumerate(self._columns):
            value -= self._widths.get(column, 110)
            if value < 0: return '#' + str(index+1)
        return ''

    def bbox(self, iid, column):
        if str(iid) not in self._rows or column not in self._columns: return ''
        index = self._columns.index(column)
        x = self.GUTTER + sum(self._widths.get(c,110) for c in self._columns[:index]) - self._x
        y = self.HEADER + self._order.index(str(iid))*self.ROW - self._y
        width = self._widths.get(column,110)
        if x < self.GUTTER or x >= self.winfo_width() or y < self.HEADER or y >= self.winfo_height(): return ''
        return int(x),int(y),int(min(width,self.winfo_width()-x)),self.ROW

    def see(self, iid):
        if str(iid) not in self._rows: return
        top = self._order.index(str(iid))*self.ROW
        available = max(1,self.winfo_height()-self.HEADER)
        if top < self._y: self._y = top
        elif top+self.ROW > self._y+available: self._y = top+self.ROW-available
        self._redraw()

    def see_cell(self,iid,column):
        self.see(iid)
        if not 0 <= column < len(self._columns): return
        left=sum(self._widths.get(c,110) for c in self._columns[:column])
        width=self._widths.get(self._columns[column],110)
        available=max(1,self.winfo_width()-self.GUTTER)
        if left < self._x: self._x=left
        elif left+width > self._x+available: self._x=left+width-available
        self._redraw()

    def _view(self, axis, args):
        total = sum(self._widths.get(c,110) for c in self._columns) if axis == 'x' else len(self._order)*self.ROW
        available = max(1,(self.winfo_width()-self.GUTTER) if axis == 'x' else (self.winfo_height()-self.HEADER))
        offset = self._x if axis == 'x' else self._y
        if not args: return offset/max(1,total),min(1,(offset+available)/max(1,total))
        if args[0] == 'moveto': offset = float(args[1])*total
        else: offset += int(args[1])*(available*.9 if args[2] == 'pages' else (self.ROW if axis == 'y' else 35))
        offset = max(0,min(offset,max(0,total-available)))
        if axis == 'x': self._x = offset
        else: self._y = offset
        self._redraw()

    def xview(self, *args): return self._view('x',args)
    def yview(self, *args): return self._view('y',args)

    def _wheel(self, event):
        self.yview('scroll', -int(event.delta/120)*3, 'units')
        return 'break'

    def _redraw(self):
        if not self._pending:
            self._pending = True; self._paint_id = self.after_idle(self._paint)

    def _paint(self):
        self._pending = False
        self._paint_id = None
        super().delete('all')
        width,height = self.winfo_width(),self.winfo_height()
        self._x = max(0,min(self._x,max(0,sum(self._widths.get(c,110) for c in self._columns)-(width-self.GUTTER))))
        self._y = max(0,min(self._y,max(0,len(self._order)*self.ROW-(height-self.HEADER))))
        start = max(0,int(self._y//self.ROW))
        stop = min(len(self._order),start+max(1,math.ceil((height-self.HEADER)/self.ROW))+1)
        positions=[]; x=self.GUTTER-self._x
        for index,column in enumerate(self._columns):
            cell_width=self._widths.get(column,110)
            if x+cell_width > self.GUTTER and x < width: positions.append((index,column,x,cell_width))
            x += cell_width
        for row in range(start,stop):
            iid=self._order[row]; y=self.HEADER+row*self.ROW-self._y
            label,values=self._rows[iid]
            for index,column,x,cell_width in positions:
                selected = iid in self._selected and (self._selection_columns is None or self._selection_columns[0] <= index <= self._selection_columns[1])
                self.create_rectangle(x,y,x+cell_width,y+self.ROW,fill='#e7f1f7' if selected else 'white',outline='#dddddd')
                value=str(values[index]) if index < len(values) else ''
                limit=max(1,int((cell_width-12)/7))
                if len(value)>limit: value=value[:max(1,limit-1)]+'…'
                self.create_text(x+7,y+self.ROW/2,text=value,anchor='w',font=('Segoe UI',9),fill='#202020')
                if iid==self._focused and index==self._active_column:
                    self.create_rectangle(x+1,y+1,x+cell_width-1,y+self.ROW-1,outline='#087c9a',width=2)
            self.create_rectangle(0,y,self.GUTTER,y+self.ROW,fill='#f1f1f1',outline='#d4d4d4')
            self.create_text(self.GUTTER-7,y+self.ROW/2,text=label,anchor='e',font=('Segoe UI',9),fill='#454545')
        self.create_rectangle(0,0,width,self.HEADER,fill='#f1f1f1',outline='#c8c8c8')
        for index,column,x,cell_width in positions:
            self.create_rectangle(x,0,x+cell_width,self.HEADER,fill='#f1f1f1',outline='#c8c8c8')
            title=self._headings.get(column,column).split('\n',1)
            self.create_text(x+7,11,text=title[0],anchor='w',font=('Segoe UI',9),fill='#444444')
            self.create_text(x+7,30,text=(title[1] if len(title)>1 else '')[:int((cell_width-12)/7)],anchor='w',font=('Segoe UI',9),fill='#202020')
        self.create_rectangle(0,0,self.GUTTER,self.HEADER,fill='#e8e8e8',outline='#c8c8c8')
        if self._xcommand: self._xcommand(*self.xview())
        if self._ycommand: self._ycommand(*self.yview())
