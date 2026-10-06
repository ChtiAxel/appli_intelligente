-- ============================================================
-- NaturSQL - Script d'initialisation de sécurité MariaDB
-- Création du compte utilisateur restreint en Lecture Seule
-- ============================================================

-- 1. Création de l'utilisateur lecture seule
CREATE USER IF NOT EXISTS 'natursql_readonly'@'%' IDENTIFIED BY 'readonly_secret';
CREATE USER IF NOT EXISTS 'natursql_readonly'@'localhost' IDENTIFIED BY 'readonly_secret';

-- 2. Révocation stricte de tous les privilèges préalables
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'natursql_readonly'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'natursql_readonly'@'localhost';

-- 3. Attribution des droits SELECT UNIQUEMENT sur les tables et vues pédagogiques
GRANT SELECT ON `appia`.`enseignants` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`enseignants` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`cours` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`cours` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`seances` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`seances` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`maquette` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`maquette` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`possede` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`possede` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`competences` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`competences` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`formations` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`formations` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`formation_groupe` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`formation_groupe` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`semaines` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`semaines` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`statut` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`statut` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`type_seance` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`type_seance` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`volume_pn` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`volume_pn` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`details` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`details` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`annee_scolaire` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`annee_scolaire` TO 'natursql_readonly'@'localhost';
GRANT SELECT ON `appia`.`maquette_ens` TO 'natursql_readonly'@'%';
GRANT SELECT ON `appia`.`maquette_ens` TO 'natursql_readonly'@'localhost';

-- 4. Actualisation des privilèges
FLUSH PRIVILEGES;
