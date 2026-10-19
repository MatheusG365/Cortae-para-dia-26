import React from "react";
import { useSession } from "../../lib/session";
import { Button, Card, Screen } from "../../ui";
import { Copy, Heading, confirmAction, go } from "./shared";
export default function OwnerMore() {
  const { user, signOut } = useSession();
  return (
    <Screen
      title="Gestão da barbearia"
      subtitle="Tudo para acompanhar o seu negócio."
    >
      <Card>
        <Heading>{user?.nome}</Heading>
        <Copy muted>{user?.email}</Copy>
      </Card>
      {[
        ["Equipe e serviços", "equipe"],
        ["Clientes e histórico", "clientes"],
        ["Caixa e comissões", "financeiro"],
        ["Ranking e avaliações", "ranking"],
        ["Metas dos profissionais", "metas"],
        ["Relatórios de atendimentos", "relatorios"],
        ["Pedidos e entregas", "pedidos"],
        ["Vendas da loja", "vendas"],
        ["Fornecedores", "fornecedores"],
        ["Cupons de desconto", "cupons"],
        ["Perfil e regras da barbearia", "perfil"],
      ].map(([title, path]) => (
        <Button
          key={path}
          title={title}
          variant="secondary"
          onPress={() => go(`/barbearia/${path}`)}
        />
      ))}
      <Button
        title="Termos de Uso"
        variant="ghost"
        onPress={() => go("/termos")}
      />
      <Button
        title="Sair da conta"
        variant="danger"
        onPress={() =>
          confirmAction(
            "Sair do aplicativo?",
            "Você precisará entrar novamente para acessar a barbearia.",
            () => {
              void signOut();
            },
          )
        }
      />
    </Screen>
  );
}
