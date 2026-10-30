"""Synthetic worksheet fixture for exercising the new formula/color workflow."""
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column

p=Presenter()
p.worksheet=Worksheet('Formula workflow',[Column('Input',values=[2,4,6,8,10]),Column('Adjusted'),Column('Twice')])
p.assign_formula(2,'C1*2');p.assign_formula(1,'C3+1')
p.set_cell_highlight([1],[1],'#d4edda')
p.apply_conditional_formatting(1,'greater_than',10,color='#f8d7da')
p.add_worksheet('Other worksheet');p.paste(0,0,'1\n2\n3\n')
p.rename_column(0,'Source');p.rename_column(1,'Calculated');p.assign_formula(1,'C1+10')
p.select_worksheet(0)
destination=Path(__file__).resolve().parents[2]/'outputs/StatCraft-formula-workflow-demo.mpx'
p.save(destination)
print(destination)
