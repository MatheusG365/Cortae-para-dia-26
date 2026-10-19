import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';

import Header from './components/Header/header';
import Footer from './components/Footer/footer';
import RequireAuth from './components/RequireAuth/RequireAuth';
import { AuthProvider } from './contexts/AuthContext';

const Home = lazy(() => import('./pages/Home/Home'));
const Login = lazy(() => import('./pages/Login/login'));
const Cadastro = lazy(() => import('./pages/Cadastro/cadastro'));
const RedefinirSenha = lazy(() => import('./pages/RedefinacaoSenha/RedefinacaoSenha'));
const EditarUsuario = lazy(() => import('./pages/EditarUsuario/EditarUsuario'));
const VerificarCodigo = lazy(() => import('./pages/VerificarCodigo/VerificarCodigo'));
const Estabelecimento = lazy(() => import('./pages/Estabelecimento/Estabelecimento'));
const CadastroBarbearia = lazy(() => import('./pages/CadastroBarbearia/CadastroBarbearia.jsx'));
const BarbeariasDisponiveis = lazy(() => import('./pages/BarbeariasDisponiveis/BarbeariasDisponiveis'));
const Erro = lazy(() => import('./pages/Erro/Erro'));
const PersonalizacaoBarbearia = lazy(() => import('./pages/PersonalizacaoBarbearia/PersonalizacaoBarbearia.jsx'));
const EditarBarbearia = lazy(() => import('./pages/EditarBarbearia/EditarBarbearia.jsx'));
const AdminUsuarios = lazy(() => import('./pages/AdminUsuarios/AdminUsuarios.jsx'));
const AdminCortes = lazy(() => import('./pages/AdminCortes/AdminCortes.jsx'));
const Visagismo = lazy(() => import('./pages/Visagismo/Visagismo.jsx'));
const Agendamento = lazy(() => import('./pages/Agendamento/Agendamento.jsx'));
const AdminFinanceiro = lazy(() => import('./pages/AdminFinanceiro/AdminFinanceiro.jsx'));
const SelecionarServicos = lazy(() => import('./pages/SelecionarServicos/SelecionarServicos.jsx'));
const MeusAgendamentos = lazy(() => import('./pages/MeusAgendamentos/MeusAgendamentos.jsx'));
const AgendamentosAdm = lazy(() => import('./pages/agendamentosadm/agendamentosadm.jsx'));
const PainelBarbeiro = lazy(() => import('./pages/PainelBarbeiro/PainelBarbeiro.jsx'));
const AtivarBarbeiro = lazy(() => import('./pages/AtivarBarbeiro/AtivarBarbeiro.jsx'));
const ComissoesBarbearia = lazy(() => import('./pages/ComissoesBarbearia/ComissoesBarbearia.jsx'));
const Gestao = lazy(() => import('./pages/Gestao/Gestao.jsx'));
const HelpAdmin = lazy(() => import('./pages/HelpAdmin/HelpAdmin.jsx'));
const MarketplaceCatalogo = lazy(() => import('./pages/Marketplace/MarketplaceCatalogo.jsx'));
const MarketplaceLoja = lazy(() => import('./pages/Marketplace/MarketplaceLoja.jsx'));
const MarketplaceProduto = lazy(() => import('./pages/Marketplace/MarketplaceProduto.jsx'));
const MarketplaceCarrinho = lazy(() => import('./pages/Marketplace/MarketplaceCarrinho.jsx'));
const MarketplacePedidos = lazy(() => import('./pages/Marketplace/MarketplacePedidos.jsx'));
const GestaoMarketplace = lazy(() => import('./pages/Marketplace/GestaoMarketplace.jsx'));
const TermosUso = lazy(() => import('./pages/TermosUso/TermosUso.jsx'));

export default function App() {
    return (
        <AuthProvider>
            <Header />

            <Suspense fallback={<div className="carregamento-pagina" role="status">Carregando página…</div>}>
            <Routes>
                <Route path="/termos-de-uso" element={<TermosUso />} />
                <Route path="/marketplace" element={<MarketplaceCatalogo />} />
                <Route path="/marketplace/barbearias/:id_barbearia" element={<MarketplaceLoja />} />
                <Route path="/marketplace/produtos/:id" element={<MarketplaceProduto />} />
                <Route path="/marketplace/lista-desejos" element={<RequireAuth tipos={[1]}><MarketplaceCatalogo desejos /></RequireAuth>} />
                <Route path="/marketplace/favoritos" element={<RequireAuth tipos={[1]}><MarketplaceCatalogo favoritos /></RequireAuth>} />
                <Route path="/marketplace/carrinho" element={<RequireAuth tipos={[1]}><MarketplaceCarrinho /></RequireAuth>} />
                <Route path="/marketplace/pedidos" element={<RequireAuth tipos={[1]}><MarketplacePedidos /></RequireAuth>} />
                <Route path="/marketplace/pedidos/:id" element={<RequireAuth tipos={[1]}><MarketplacePedidos /></RequireAuth>} />
                <Route path="/gestao-marketplace" element={<RequireAuth tipos={[0, 2]}><GestaoMarketplace /></RequireAuth>} />
                <Route path="/help" element={<RequireAuth tipos={[0]}><HelpAdmin /></RequireAuth>} />
                <Route path="/gestao" element={<RequireAuth tipos={[0, 2, 3]}><Gestao /></RequireAuth>} />
                <Route path="/painel-barbeiro" element={<RequireAuth tipos={[3]}><PainelBarbeiro /></RequireAuth>} />
                <Route path="/comissoes-barbearia" element={<RequireAuth tipos={[0, 2]}><ComissoesBarbearia /></RequireAuth>} />
                <Route path="/ativar-barbeiro" element={<AtivarBarbeiro />} />
                <Route
                    path="/*"
                    element={<Erro />}
                />
                <Route
                    path="/"
                    element={<Home />}
                />

                <Route
                    path="/login"
                    element={<Login />}
                />

                <Route
                    path="/cadastro"
                    element={<Cadastro />}
                />

                <Route
                    path="/redefinirsenha"
                    element={<RedefinirSenha />}
                />

                <Route
                    path="/editarusuario"
                    element={<RequireAuth><EditarUsuario /></RequireAuth>}
                />

                <Route
                    path="/verificar-codigo"
                    element={<VerificarCodigo />}
                />

                <Route
                    path="/estabelecimento"
                    element={<Estabelecimento />}
                />

                <Route
                    path="/barbearias-disponiveis"
                    element={<BarbeariasDisponiveis />}
                />

                <Route
                    path="/cadastrobarbearia"
                    element={<RequireAuth tipos={[0]}><CadastroBarbearia /></RequireAuth>}
                />

                <Route
                    path="/personalizacaobarbearia"
                    element={<RequireAuth tipos={[0, 2]}><PersonalizacaoBarbearia /></RequireAuth>}
                />

                <Route
                    path="/editarbarbearia"
                    element={<RequireAuth tipos={[0, 2]}><EditarBarbearia /></RequireAuth>}
                />

                <Route path="/visagismo" element={<RequireAuth><Visagismo /></RequireAuth>} />

                <Route path="/selecionar-servicos" element={<RequireAuth><SelecionarServicos /></RequireAuth>} />

                <Route path="/agendamento" element={<RequireAuth><Agendamento /></RequireAuth>} />

                <Route path="/meus-agendamentos" element={<RequireAuth><MeusAgendamentos /></RequireAuth>} />

                <Route path="/agendamentosadm" element={<RequireAuth tipos={[0, 2]}><AgendamentosAdm /></RequireAuth>} />

                <Route path="/financeiro" element={<RequireAuth tipos={[0, 2]}><AdminFinanceiro /></RequireAuth>} />

                <Route path="/admin/usuarios" element={<RequireAuth tipos={[0]}><AdminUsuarios /></RequireAuth>} />
                <Route path="/admin/cortes" element={<RequireAuth tipos={[0, 2]}><AdminCortes /></RequireAuth>} />
                <Route path="/editarusuario/:id" element={<RequireAuth><EditarUsuario /></RequireAuth>} />


            </Routes>
            </Suspense>

            <Footer />
        </AuthProvider>
    );
}

