"""Saved native output parsing tests use wholly authored package fragments."""
import copy
import json
import unittest
from statcraft.native_mpx_outputs import read_outputs, _Reader, _report


def vector(values):
    key = 'TextData' if values and isinstance(values[0], str) else 'NumericData'
    return {'WorksheetVar': {'WorksheetVarBody': {'VarData': {'VarDataBody': {key: values}}}}}


def fixture():
    model = {'XCol': vector([1., 2., 3.]), 'YCol': vector([4., 6., 8.])}
    figure = {'GraphModels': [model], 'Panels': [{'GraphModels': [0]}],
              'DataRepList': [{'GraphType': 1, 'DataReps': [{'Key': 32, 'Value': {'Tag': 'Symbols', 'Show': True}}]}]}
    graph = {'Graph': {'Title': 'Saved original graph', 'FigureList': [{'Figures': [figure]}]}}
    group = {'Id': 'g1', 'Outputs': [{'Data': {'Base': 'Saved original report'}, 'GraphDoc': '/commands/1/graphs/3/graph'}]}
    metadata = {'Worksheets': {'Items': [{'Id': 'w1', 'Name': 'First sheet'}]},
                'Commands': {'Items': [{'Id': 'c1', 'OutputWorksheet': 'w1', 'Executed': '2026-01-01',
                                        'OutputGroups': [{'Title': 'Native analysis', 'Uri': '/commands/1/groups/2/group'}]}]}}
    return metadata, {'/commands/1/groups/2/group.json': json.dumps(group).encode(),
                      '/commands/1/graphs/3/graph.json': json.dumps(graph).encode()}, graph, figure, group


def update(members, path, obj):
    members[path] = json.dumps(obj).encode()


class NativeSavedOutputTests(unittest.TestCase):
    def test_group_identity_order_and_native_origin(self):
        meta, members, *_ = fixture()
        e = read_outputs(meta, members)[0]
        self.assertEqual((e['origin'], e['worksheet_id'], e['worksheet_name']), ('native', 'w1', 'First sheet'))
        self.assertEqual(e['entry_id'], 'native:c1:g1')
        self.assertNotIn('recipe', e)

    def test_saved_values_are_not_recomputed(self):
        meta, members, *_ = fixture()
        p = read_outputs(meta, members)[0]['result']['graphs'][0]['panels'][0]
        self.assertEqual(p['series'][0]['y'], [4., 6., 8.])

    def test_source_inputs_unchanged(self):
        meta, members, *_ = fixture(); before = copy.deepcopy((meta, members))
        read_outputs(meta, members)
        self.assertEqual((meta, members), before)

    def test_empty_graph_reference_means_report_only(self):
        meta, members, graph, figure, group = fixture()
        group['Outputs'][0]['GraphDoc'] = ''; update(members, '/commands/1/groups/2/group.json', group)
        self.assertEqual(read_outputs(meta, members)[0]['result']['graphs'], [])

    def test_missing_group_is_visible_warning(self):
        meta, members, *_ = fixture(); members.pop('/commands/1/groups/2/group.json')
        self.assertIn('missing or unreadable', read_outputs(meta, members)[0]['result']['text'])

    def test_missing_graph_keeps_visible_warning(self):
        meta, members, *_ = fixture(); members.pop('/commands/1/graphs/3/graph.json')
        self.assertIn('missing or unreadable', read_outputs(meta, members)[0]['result']['graphs'][0]['warnings'][0])

    def test_hidden_outputs_omitted(self):
        meta, members, graph, figure, group = fixture(); group['Outputs'][0]['Visible'] = False
        update(members, '/commands/1/groups/2/group.json', group)
        self.assertEqual(read_outputs(meta, members)[0]['result']['graphs'], [])

    def test_duplicate_graph_reference_deduplicated(self):
        meta, members, graph, figure, group = fixture(); group['Outputs'] *= 2
        update(members, '/commands/1/groups/2/group.json', group)
        self.assertEqual(len(read_outputs(meta, members)[0]['result']['graphs']), 1)

    def test_nested_outputs_read(self):
        meta, members, graph, figure, group = fixture(); group['Outputs'] = [{'Outputs': group['Outputs']}]
        update(members, '/commands/1/groups/2/group.json', group)
        self.assertEqual(len(read_outputs(meta, members)[0]['result']['graphs']), 1)

    def test_unknown_worksheet_not_misassigned(self):
        meta, members, *_ = fixture(); meta['Commands']['Items'][0]['OutputWorksheet'] = 'gone'
        self.assertEqual(read_outputs(meta, members), [])

    def test_input_worksheet_fallback(self):
        meta, members, *_ = fixture(); meta['Commands']['Items'][0]['InputWorksheet'] = 'w1';meta['Commands']['Items'][0]['OutputWorksheet'] = ''
        self.assertEqual(read_outputs(meta, members)[0]['worksheet_id'], 'w1')

    def test_cross_member_figure_reference(self):
        meta, members, graph, figure, group = fixture()
        graph['Graph']['FigureList'][0]['Figures'] = ['/commands/1/figures/4/figure/Figure']
        update(members, '/commands/1/graphs/3/graph.json', graph);update(members, '/commands/1/figures/4/figure.json', {'Figure': figure})
        self.assertEqual(len(read_outputs(meta, members)[0]['result']['graphs'][0]['panels']), 1)

    def test_reference_cycle_is_bounded(self):
        reader = _Reader({'/cycle.json': b'{"next":"/cycle/next"}'})
        self.assertIsNone(reader.resolve('/cycle/next'))

    def test_unsafe_reference_never_reads_filesystem(self):
        self.assertIsNone(_Reader({}).resolve('/../../Windows/system32'))

    def test_contour_grid_and_native_palette(self):
        meta, members, graph, figure, group = fixture()
        figure['GraphModels'][0]['ContourGrid'] = {'XMesh': [1,2], 'YMesh': [3,4], 'ZValues': [5,6,7,8]}
        figure['ContourLevelsC'] = [6,7]
        figure['Legends'] = [{'LegendSection': [{'LegendGeomGroups': [{'DataRepState': {'FillAttrib': {'FillRGBA': ['a7e5bcff','80cd8fff']}}}]}]}]
        update(members, '/commands/1/graphs/3/graph.json', graph)
        p = read_outputs(meta,members)[0]['result']['graphs'][0]['panels'][0]
        self.assertEqual(p['grid']['z'], [[5,6],[7,8]])
        self.assertEqual(p['colors'], ['#a7e5bc','#80cd8f'])

    def test_bad_grid_not_invented(self):
        meta, members, graph, figure, group = fixture()
        figure['GraphModels'][0]['ContourGrid'] = {'XMesh':[1,2], 'YMesh':[3,4], 'ZValues':[5]}
        update(members, '/commands/1/graphs/3/graph.json', graph)
        self.assertFalse(read_outputs(meta,members)[0]['result']['graphs'][0]['panels'])

    def test_surface_grid_retains_original_values(self):
        meta, members, graph, figure, group = fixture()
        figure['GraphModels'][0]['RSPlotContourGrid'] = {'XMesh':[1,2], 'YMesh':[3,4], 'ZValues':[5,6,7,8]}
        update(members, '/commands/1/graphs/3/graph.json', graph)
        p = read_outputs(meta,members)[0]['result']['graphs'][0]['panels'][0]
        self.assertEqual(p['kind'],'surface');self.assertEqual(p['grid']['z'][1][1],8)

    def test_probability_explicitly_marks_reconstructed_ranks(self):
        meta, members, graph, figure, group = fixture()
        figure['GraphModels'][0]['YCol'] = {};figure['GraphModels'][0]['Parameters'] = [[12.,3.]]
        figure['DataRepList'][0]['GraphType'] = 12
        figure['FigureState'] = {'DistributionType': {'DistributionType': 1}}
        update(members, '/commands/1/graphs/3/graph.json', graph)
        g = read_outputs(meta,members)[0]['result']['graphs'][0]
        self.assertIn('reconstructed',g['warnings'][0]);self.assertEqual(g['panels'][0]['kind'],'probability')
        self.assertEqual(g['panels'][0]['series'][0]['x'],[1.,2.,3.])

    def test_table_labels_percentage_and_equation(self):
        data={'Titles':[{'Value':{'Base':'Model Summary'}}], 'TableCol':[
            {'Value':{'UnformattedLabels':[{'Label':'R-sq'}], 'Values':[.85],
                      'Format':{'Value':{'Subtype':4,'NumericFmtSubtype':{'DecimalPlaces':2}}}}},
            {'Value':{'UnformattedLabels':[{'Label':'Equation'}], 'Cells':[{'Value':{'FormattedLines':['Y = 2 + 3 X']}}]}}
        ]}
        text=_report(data)
        for expected in ['Model Summary','R-sq','85.00%','Y = 2 + 3 X']:self.assertIn(expected,text)

    def test_unexpanded_sentence_template_not_displayed(self):
        self.assertEqual(_report({'Base':'response %1, alpha %2'}),'')

    def test_line_breaks_preserve_stored_curves(self):
        meta, members, graph, figure, group = fixture()
        figure['GraphModels'][0].update(XCol=vector([1,2,1,2]),YCol=vector([5,6,7,8]))
        figure['DataRepList'][0]['DataReps']=[{'Key':12,'Value':{'Tag':'Connect Line','Show':True}}]
        update(members,'/commands/1/graphs/3/graph.json',graph)
        p=read_outputs(meta,members)[0]['result']['graphs'][0]['panels'][0]
        self.assertEqual([s['y'] for s in p['series']],[[5,6],[7,8]])

    def test_nan_and_missing_sentinels_not_geometry(self):
        meta,members,graph,figure,group=fixture()
        figure['GraphModels'][0]['YCol']=vector([4.,1.23456e30,8.])
        update(members,'/commands/1/graphs/3/graph.json',graph)
        s=read_outputs(meta,members)[0]['result']['graphs'][0]['panels'][0]['series'][0]
        self.assertEqual(s['x'],[1.,3.])

if __name__ == '__main__':unittest.main()
