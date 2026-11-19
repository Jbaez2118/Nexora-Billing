import { useState } from 'react';
import { Button, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

const API = process.env.EXPO_PUBLIC_API_URL;
const LABEL: Record<string, string> = { required: 'Requeridas', recommended: 'Recomendadas', optional: 'Opcionales', future: 'Futuras' };
const NUM: [string, string][] = [['workforce', 'Trabajadores'], ['branches', 'Sucursales'], ['registers', 'Cajas'], ['orders_per_day', 'Pedidos por día'], ['sku_count', 'Cantidad de artículos'], ['growth_branches', 'Sucursales nuevas previstas']];
const FLAG: [string, string][] = [['has_delivery', 'Entrega a domicilio'], ['has_returns', 'Devoluciones'], ['has_production', 'Producción'], ['perishables', 'Perecederos']];
const INDUSTRY: [string, string][] = [['retail_general', 'Minorista'], ['wholesale', 'Mayorista']];
const RISK: [string, string][] = [['low', 'Bajo'], ['medium', 'Medio'], ['high', 'Alto']];

type Item = { capability_id: string; name: string; classification: string; rationale: string[] };
type Result = { template: { name: string; version: number }; items: Item[]; assumptions: string[]; org: { stage: string; units: string[]; notes: string[] }; ruleset_version: string };

function Choice({ opts, value, onChange }: { opts: [string, string][]; value: string; onChange: (v: string) => void }) {
  return (
    <View style={s.row}>
      {opts.map(([k, l]) => (
        <Pressable key={k} onPress={() => onChange(k)} style={[s.chip, value === k && s.chipOn]}>
          <Text style={value === k ? s.chipTxtOn : undefined}>{l}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function Oibc({ token }: { token: string }) {
  const [f, setF] = useState<Record<string, any>>({ industry: 'retail_general', risk_level: 'low', workforce: '10', branches: '1', registers: '1', orders_per_day: '0', sku_count: '0', growth_branches: '0' });
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState('');
  const set = (k: string, v: any) => setF(p => ({ ...p, [k]: v }));

  async function submit() {
    setErr('');
    const body: Record<string, any> = { industry: f.industry, risk_level: f.risk_level };
    NUM.forEach(([k]) => { body[k] = Number(f[k] || 0); });
    // workforce_invalid: el API exige industry no vacía y workforce >= 1
    if (!f.industry) return setErr('Seleccione una industria');
    if (!Number.isInteger(body.workforce) || body.workforce < 1) return setErr('Indique la cantidad de personal (mínimo 1)');
    FLAG.forEach(([k]) => { body[k] = !!f[k]; });
    try {
      const r = await fetch(`${API}/oibc/assessments`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body) });
      if (!r.ok) { const t = await r.text(); return setErr('Error ' + r.status + ' ' + t.slice(0, 200)); }
      setRes((await r.json()).result);
    } catch (e) { setErr(String(e)); }
  }

  return (
    <View style={{ marginTop: 24 }}>
      <Text style={s.h2}>Evaluación del negocio</Text>
      <Text style={s.lbl}>Industria</Text>
      <Choice opts={INDUSTRY} value={f.industry} onChange={v => set('industry', v)} />
      <Text style={s.lbl}>Riesgo</Text>
      <Choice opts={RISK} value={f.risk_level} onChange={v => set('risk_level', v)} />
      {NUM.map(([k, l]) => (
        <View key={k}>
          <Text style={s.lbl}>{l}</Text>
          <TextInput style={s.input} keyboardType="number-pad" value={String(f[k])} onChangeText={v => set(k, v.replace(/[^0-9]/g, ''))} />
        </View>
      ))}
      {FLAG.map(([k, l]) => (
        <View key={k} style={s.sw}><Text>{l}</Text><Switch value={!!f[k]} onValueChange={v => set(k, v)} /></View>
      ))}
      <Button title="Generar recomendación" onPress={submit} />
      {!!err && <Text style={{ color: 'crimson', marginTop: 8 }}>{err}</Text>}
      {res && (
        <View style={{ marginTop: 16 }}>
          <Text style={{ fontWeight: '700' }}>{res.template.name} v{res.template.version} · etapa {res.org.stage}</Text>
          <Text style={s.h3}>Organización propuesta</Text>
          {res.org.units.map(u => <Text key={u}>• {u}</Text>)}
          {res.org.notes.map(n => <Text key={n} style={s.small}>{n}</Text>)}
          {Object.keys(LABEL).map(c => {
            const rows = res.items.filter(i => i.classification === c);
            return rows.length === 0 ? null : (
              <View key={c}>
                <Text style={s.h3}>{LABEL[c]}</Text>
                {rows.map(i => <Text key={i.capability_id} style={{ marginBottom: 4 }}><Text style={{ fontWeight: '600' }}>{i.name}: </Text>{i.rationale.join(' · ')}</Text>)}
              </View>
            );
          })}
          <Text style={s.h3}>Supuestos</Text>
          {res.assumptions.map(a => <Text key={a} style={s.small}>{a}</Text>)}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  h2: { fontSize: 18, fontWeight: '600', marginBottom: 8 },
  h3: { fontSize: 16, fontWeight: '600', marginTop: 12, marginBottom: 4 },
  lbl: { marginTop: 8, marginBottom: 4 },
  small: { fontSize: 12, color: '#555', marginTop: 2 },
  input: { borderWidth: 1, borderColor: '#bbb', borderRadius: 6, padding: 8 },
  row: { flexDirection: 'row', gap: 8 },
  chip: { borderWidth: 1, borderColor: '#bbb', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  chipOn: { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  chipTxtOn: { color: '#fff' },
  sw: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 4 },
});

