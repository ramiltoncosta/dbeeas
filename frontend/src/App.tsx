import { Route, Routes } from 'react-router-dom'
import { LayoutApp, LayoutConta, LayoutPublico, SomenteAdmin, SomenteVisitante } from './components/Layouts'
import AdminUsuarios from './pages/admin/Usuarios'
import { Cadastrar, Entrar, EsqueciSenha, RedefinirSenha } from './pages/Conta'
import MinhaConta from './pages/MinhaConta'
import Painel from './pages/Painel'
import { Inicio, NaoEncontrada, Privacidade, Termos } from './pages/Publicas'

export default function App() {
  return (
    <Routes>
      <Route element={<LayoutPublico />}>
        <Route path="/" element={<Inicio />} />
        <Route path="/termos" element={<Termos />} />
        <Route path="/privacidade" element={<Privacidade />} />
      </Route>

      <Route element={<LayoutConta />}>
        <Route element={<SomenteVisitante />}>
          <Route path="/entrar" element={<Entrar />} />
          <Route path="/cadastrar" element={<Cadastrar />} />
        </Route>
        <Route path="/esqueci-senha" element={<EsqueciSenha />} />
        <Route path="/redefinir-senha" element={<RedefinirSenha />} />
      </Route>

      <Route element={<LayoutApp />}>
        <Route path="/painel" element={<Painel />} />
        <Route path="/conta" element={<MinhaConta />} />
        <Route element={<SomenteAdmin />}>
          <Route path="/admin/usuarios" element={<AdminUsuarios />} />
        </Route>
      </Route>

      <Route element={<LayoutPublico />}>
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}
