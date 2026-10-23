import { Navigate, Route, Routes } from 'react-router-dom'
import { LayoutApp, LayoutConformeSessao, LayoutConta, LayoutPublico, SomenteAdmin, SomenteVisitante } from './components/Layouts'
import AdminMensagens from './pages/admin/Mensagens'
import FichaEditor from './pages/admin/FichaEditor'
import Catalogo from './pages/especies/Catalogo'
import FichaEspecie from './pages/especies/Ficha'
import AdminUsuarios from './pages/admin/Usuarios'
import FormularioColeta from './pages/coletas/Formulario'
import DetalheColeta from './pages/coletas/Detalhe'
import ListaColetas from './pages/coletas/Lista'
import { Cadastrar, Entrar, EsqueciSenha, RedefinirSenha } from './pages/Conta'
import Identificar from './pages/Identificar'
import Mapa from './pages/Mapa'
import AdminEspecies from './pages/admin/Especies'
import MinhaConta from './pages/MinhaConta'
import Painel from './pages/Painel'
import Inicio from './pages/Inicio'
import { NaoEncontrada, Privacidade, Termos } from './pages/Publicas'

export default function App() {
  return (
    <Routes>
      <Route element={<LayoutPublico />}>
        <Route path="/" element={<Inicio />} />
        <Route path="/termos" element={<Termos />} />
        <Route path="/privacidade" element={<Privacidade />} />
      </Route>

      {/* Abertas ao público; quem está logado vê com o menu do sistema */}
      <Route element={<LayoutConformeSessao />}>
        <Route path="/especies" element={<Catalogo />} />
        <Route path="/especies/:id" element={<FichaEspecie />} />
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
        <Route path="/coletas" element={<ListaColetas />} />
        <Route path="/coletas/nova" element={<FormularioColeta />} />
        <Route path="/coletas/:id" element={<DetalheColeta />} />
        <Route path="/coletas/:id/editar" element={<FormularioColeta />} />
        <Route path="/identificar" element={<Identificar />} />
        <Route path="/mapa" element={<Mapa />} />
        <Route path="/conta" element={<MinhaConta />} />
        <Route element={<SomenteAdmin />}>
          <Route path="/admin/usuarios" element={<AdminUsuarios />} />
          <Route path="/admin" element={<Navigate to="/admin/usuarios" replace />} />
          <Route path="/admin/especies" element={<AdminEspecies />} />
          <Route path="/admin/especies/:id/ficha" element={<FichaEditor />} />
          <Route path="/admin/mensagens" element={<AdminMensagens />} />
        </Route>
      </Route>

      <Route element={<LayoutPublico />}>
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  )
}
