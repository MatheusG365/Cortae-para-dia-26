import MarketplaceCatalogo from './MarketplaceCatalogo';

// O catálogo completo faz parte do estabelecimento; não abre uma segunda loja.
export default function LojaBarbeariaPreview({ idLoja }) {
    return idLoja ? <MarketplaceCatalogo key={idLoja} idLoja={idLoja} embutido /> : null;
}
