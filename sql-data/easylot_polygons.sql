-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: 173.81.182.227    Database: easylot
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `polygons`
--

DROP TABLE IF EXISTS `polygons`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `polygons` (
  `id` int NOT NULL AUTO_INCREMENT,
  `spot_id` int NOT NULL,
  `points_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `spot_id` (`spot_id`),
  CONSTRAINT `polygons_ibfk_1` FOREIGN KEY (`spot_id`) REFERENCES `spots` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `polygons`
--

LOCK TABLES `polygons` WRITE;
/*!40000 ALTER TABLE `polygons` DISABLE KEYS */;
INSERT INTO `polygons` VALUES (49,49,'[[160.0, 611.0], [540.0, 595.0], [541.0, 686.0], [173.0, 702.0]]'),(50,50,'[[545.0, 592.0], [903.0, 567.0], [940.0, 675.0], [548.0, 682.0]]'),(51,51,'[[196.0, 531.0], [533.0, 519.0], [541.0, 595.0], [161.0, 610.0]]'),(52,52,'[[541.0, 512.0], [868.0, 492.0], [901.0, 568.0], [551.0, 588.0]]'),(54,54,'[[540.0, 450.0], [821.0, 430.0], [845.0, 488.0], [543.0, 506.0]]'),(55,55,'[[231.0, 463.0], [533.0, 448.0], [529.0, 516.0], [203.0, 523.0]]'),(56,56,'[[535.0, 391.0], [793.0, 382.0], [800.0, 424.0], [543.0, 443.0]]'),(58,58,'[[451.0, 508.0], [523.0, 535.0], [477.0, 568.0], [389.0, 548.0]]'),(59,59,'[[317.0, 496.0], [407.0, 531.0], [297.0, 590.0], [164.0, 594.0]]'),(60,60,'[[180.0, 500.0], [228.0, 550.0], [143.0, 604.0], [48.0, 579.0]]'),(61,61,'[[257.0, 403.0], [531.0, 388.0], [539.0, 444.0], [219.0, 462.0]]'),(65,65,'[[283.0, 352.0], [535.0, 348.0], [533.0, 390.0], [264.0, 398.0]]'),(66,66,'[[548.0, 348.0], [793.0, 335.0], [788.0, 379.0], [540.0, 388.0]]');
/*!40000 ALTER TABLE `polygons` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-11-05 22:02:26
