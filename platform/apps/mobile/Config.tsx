import { useCallback, useEffect, useState } from 'react';
import { Button, StyleSheet, Text, View } from 'react-native';

const API = process.env.EXPO_PUBLIC_API_URL;
type V = { id: string; version: number; proposed_by: string; result: { template: { name: string }; org: { units: string[] }; items: { classification: string }[] } };
type Cfg = { approved: V | null; proposed: V[] };

export default function Config({ token }: { token: string }) {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [msg, setMsg] = useState('');
  const H = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/oibc/config`, { headers: H });
      if (r.ok) setCfg(await r.json());
    } catch (e) { setMsg(String(e)); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  async function call(path: string, ok: string) {
    setMsg('');
    try {
      const r = await fetch(`${API}/oibc${path}`, { method: 'POST', headers: H });
      setMsg(r.ok ? ok : r.status === 403 ? 'Sin permiso: requiere el rol org_admin' : 'Error ' + r.status);
    } catch (e) { setMsg(String(e)); }
    await load();
  }

  async function proposeLatest() {
    try {
      const r = await fetch(`${API}/oibc/assessments/latest`, { headers: H });
      if (!r.ok) return setMsg('Primero genere una recomendación');
      await call(`/runs/${(await r.json()).run_id}/proposal`, 'Propuesta registrada');
    } catch (e) { setMsg(String(e)); }
  }

  const card = (v: V, actions: boolean) => (
    <View key={v.id} style={s.card}>
      <Text style={{ fontWeight: '700' }}>v{v.version} · {v.result.template.name}</Text>
      <Text style={s.small}>Propuesta por {v.proposed_by} · {v.result.items.filter(i => i.classification === 'required').length} requeridas</Text>
      <Text style={s.small}>{v.result.org.units.join(' · ')}</Text>
      {actions && (
        <View style={s.row}>
          <Button title="Aprobar" onPress={() => call(`/proposals/${v.id}/approve`, 'Aprobada')} />
          <Button title="Rechazar" color="#b91c1c" onPress={() => call(`/proposals/${v.id}/reject`, 'Rechazada')} />
        </View>
      )}
    </View>
  );

  return (
    <View style={{ marginTop: 24, marginBottom: 48 }}>
      <Text style={s.h2}>Configuración organizacional</Text>
      <Button title="Proponer última evaluación" onPress={proposeLatest} />
      <Button title="Actualizar" onPress={load} />
      {!!msg && <Text style={{ marginTop: 8 }}>{msg}</Text>}
      <Text style={s.h3}>Aprobada (vigente)</Text>
      {cfg?.approved ? card(cfg.approved, false) : <Text style={s.small}>Aún no hay una configuración aprobada.</Text>}
      <Text style={s.h3}>Propuestas pendientes</Text>
      {cfg && cfg.proposed.length > 0 ? cfg.proposed.map(v => card(v, true)) : <Text style={s.small}>Sin propuestas pendientes.</Text>}
      <Text style={s.small}>Aprobar no activa funciones facturables.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  h2: { fontSize: 18, fontWeight: '600', marginBottom: 8 },
  h3: { fontSize: 16, fontWeight: '600', marginTop: 16, marginBottom: 4 },
  small: { fontSize: 12, color: '#555', marginTop: 2 },
  card: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, marginBottom: 8 },
  row: { flexDirection: 'row', justifyContent: 'space-around', marginTop: 8 },
});
