import { LuClock, LuScissors, LuSparkles } from 'react-icons/lu';
import styles from './Home.module.css';
import { urlImagemDoSite } from '../../services/imagensDoSite.js';

export default function Home() {
    return (
        <div className={styles.pageContainer}>
            <header className={styles.hero}>
                <div className={styles.heroOverlay}>
                    <h1 className={styles.heroTitle}>
                        LEVE A SUA BARBEARIA AO<br />PRÓXIMO ESTÁGIO.
                    </h1>

                    <div className={styles.heroCards}>

                        {/* Card 1 - Ícone de Relógio */}
                        <div id="card-agendamento-agil" className={styles.card}>
                            <div className={styles.cardIcon}>
                                <LuClock size={40} className={styles.icon} />
                            </div>
                            <h3 className={styles.cardTitle}>Agendamento ágil:</h3>
                            <p className={styles.cardText}>Reserve seu horário em minutos!</p>
                        </div>

                        {/* Card 2 - Ícone de Tesoura/Navalha */}
                        <div id="card-atendimento-tecnico" className={styles.card}>
                            <div className={styles.cardIcon}>
                                <LuScissors size={40} className={styles.icon} />
                            </div>
                            <h3 className={styles.cardTitle}>Atendimento técnico:</h3>
                            <p className={styles.cardText}>
                                No Cortaê você tem acesso às melhores barbearias!
                            </p>
                        </div>

                        {/* Card 3 - Ícone de IA/Visagismo */}
                        <div id="card-visagismo-digital" className={styles.card}>
                            <div className={styles.cardIcon}>
                                <LuSparkles size={40} className={styles.icon} />
                            </div>
                            <h3 className={styles.cardTitle}>Visagismo Digital:</h3>
                            <p className={styles.cardText}>
                                Encontra sua melhor versão aqui!
                            </p>
                        </div>

                    </div>
                </div>
            </header>

            <main className={styles.mainContent}>

                <section className={styles.section}>
                    <div className={styles.sectionMedia}>
                        <img
                            src={urlImagemDoSite('homem-com-celular.png')}
                            alt="Homem com celular"
                            className={styles.image}
                        />
                    </div>
                    <div className={styles.sectionText}>
                        <h2 className={styles.sectionTitle}>
                            Mais praticidade para<br />o seu dia a dia.
                        </h2>
                        <p className={styles.sectionParagraph}>
                            Com o Cortaê, você agenda seus compromissos onde e quando quiser.
                            Precisa remarcar ou cancelar? É simples e rápido, direto no app.
                        </p>
                    </div>
                </section>

                <section className={`${styles.section} ${styles.reverse}`}>
                    <div className={styles.sectionText}>
                        <h2 className={styles.sectionTitle}>
                            Encontre os melhores<br />profissionais aqui.
                        </h2>
                        <p className={styles.sectionParagraph}>
                            No Cortaê, você encontra as melhores opções de barbearias .
                        </p>
                        <p className={styles.sectionParagraph}>
                            Agende em segundos, economize tempo e evite preocupações.
                            Com o Cortaê, marcar e remarcar seus agendamentos nunca foi tão fácil.
                        </p>
                    </div>
                    <div className={styles.sectionMedia}>
                        <img
                            src={urlImagemDoSite('celular.png')}
                            alt="Aplicativo Cortaê"
                            className={styles.image}
                        />
                    </div>
                </section>

            </main>
        </div>
    );
}
