/*M!999999\- enable the sandbox mode */ 

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;
DROP TABLE IF EXISTS `aircraft`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `aircraft` (
  `AircraftID` int(11) NOT NULL AUTO_INCREMENT,
  `AirlineID` int(11) DEFAULT NULL,
  `FlightNumber` varchar(255) DEFAULT NULL,
  `Registration` varchar(255) DEFAULT NULL,
  `Aircraft_Type` varchar(255) DEFAULT NULL,
  `MSN` varchar(100) DEFAULT NULL,
  `Times_Seen` int(11) DEFAULT NULL,
  `Departure` varchar(255) DEFAULT NULL,
  `Arrival` varchar(255) DEFAULT NULL,
  `Country_of_Reg` varchar(255) DEFAULT NULL,
  `Country_Flag` varchar(255) DEFAULT NULL,
  `Aircraft_Image` varchar(255) DEFAULT NULL,
  `Notes` text DEFAULT NULL,
  `Age` int(11) DEFAULT NULL,
  `First_Sighted` datetime DEFAULT NULL,
  `Sightings` int(11) DEFAULT 1,
  `Timestamp` datetime DEFAULT current_timestamp(),
  `Manufacture_Year` year(4) DEFAULT NULL,
  `Manufacture_Month` tinyint(4) DEFAULT NULL,
  `Category` varchar(100) DEFAULT NULL,
  `Engine_Type` varchar(50) DEFAULT NULL,
  `Orphaned` tinyint(4) DEFAULT 0,
  `Aircraft_Updated` timestamp NOT NULL DEFAULT current_timestamp(),
  `Spotted_At` varchar(255) DEFAULT NULL,
  `ICAO_Address` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`AircraftID`),
  UNIQUE KEY `idx_unique_icao` (`ICAO_Address`),
  KEY `AirlineID` (`AirlineID`),
  CONSTRAINT `aircraft_ibfk_1` FOREIGN KEY (`AirlineID`) REFERENCES `airlines` (`AirlineID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `aircraft_images`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `aircraft_images` (
  `ImageID` int(11) NOT NULL AUTO_INCREMENT,
  `AircraftID` int(11) NOT NULL,
  `Registration` varchar(20) NOT NULL,
  `Filename` varchar(255) NOT NULL,
  `Image_Number` tinyint(4) NOT NULL DEFAULT 2,
  `Uploaded_At` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`ImageID`),
  KEY `idx_aircraft_images_aircraft_id` (`AircraftID`),
  KEY `idx_aircraft_images_registration` (`Registration`),
  CONSTRAINT `fk_aircraft_images_aircraft` FOREIGN KEY (`AircraftID`) REFERENCES `aircraft` (`AircraftID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `aircraft_owners`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `aircraft_owners` (
  `OwnerID` int(11) NOT NULL AUTO_INCREMENT,
  `AircraftID` int(11) NOT NULL,
  `AirlineID` int(11) NOT NULL,
  `From_Date` date NOT NULL,
  `To_Date` date DEFAULT NULL,
  `Notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`OwnerID`),
  KEY `AircraftID` (`AircraftID`),
  KEY `AirlineID` (`AirlineID`),
  CONSTRAINT `aircraft_owners_ibfk_1` FOREIGN KEY (`AircraftID`) REFERENCES `aircraft` (`AircraftID`) ON DELETE CASCADE,
  CONSTRAINT `aircraft_owners_ibfk_2` FOREIGN KEY (`AirlineID`) REFERENCES `airlines` (`AirlineID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `airlines`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `airlines` (
  `AirlineID` int(11) NOT NULL AUTO_INCREMENT,
  `AirlineName` varchar(255) NOT NULL,
  `Last_Updated` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `Logo` varchar(255) DEFAULT NULL,
  `Country` varchar(100) DEFAULT NULL,
  `IATA` varchar(10) DEFAULT NULL,
  `ICAO` varchar(10) DEFAULT NULL,
  `Callsign` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`AirlineID`),
  UNIQUE KEY `AirlineName` (`AirlineName`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `airports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `airports` (
  `ICAO` varchar(10) NOT NULL,
  `IATA` varchar(3) DEFAULT NULL,
  `AirportName` varchar(255) NOT NULL,
  `Country` varchar(50) NOT NULL,
  `id` int(11) NOT NULL,
  `ident` varchar(10) DEFAULT NULL,
  `type` varchar(50) DEFAULT NULL,
  `latitude_deg` decimal(10,8) DEFAULT NULL,
  `longitude_deg` decimal(11,8) DEFAULT NULL,
  `elevation_ft` int(11) DEFAULT NULL,
  `continent` varchar(2) DEFAULT NULL,
  `iso_country` varchar(2) DEFAULT NULL,
  `iso_region` varchar(10) DEFAULT NULL,
  `municipality` varchar(100) DEFAULT NULL,
  `scheduled_service` varchar(3) DEFAULT NULL,
  `gps_code` varchar(10) DEFAULT NULL,
  `local_code` varchar(10) DEFAULT NULL,
  `home_link` text DEFAULT NULL,
  `wikipedia_link` text DEFAULT NULL,
  `keywords` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_icao` (`ICAO`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `app_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `app_settings` (
  `SettingKey` varchar(100) NOT NULL,
  `SettingValue` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`SettingKey`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `argentina`;
CREATE TABLE `argentina` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `armenia`;
CREATE TABLE `armenia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `airline` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `audit_country_updates`;
CREATE TABLE `audit_country_updates` (
  `AircraftID` int(11) NOT NULL,
  `Registration` varchar(255) DEFAULT NULL,
  `Existing_Country_of_Reg` varchar(255) DEFAULT NULL,
  `Suggested_Country_of_Reg` varchar(255) DEFAULT NULL,
  `Status` enum('Pending','Approved','Rejected') DEFAULT 'Pending',
  PRIMARY KEY (`AircraftID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `australia`;
CREATE TABLE `australia` (
  `registration` varchar(10) NOT NULL,
  `aircraftmanufacturer` varchar(100) DEFAULT NULL,
  `aircraftmodel` varchar(50) DEFAULT NULL,
  `msn` varchar(50) DEFAULT NULL,
  `maxtakeoffweight` int(11) DEFAULT NULL,
  `enginecount` int(11) DEFAULT NULL,
  `enginemanufacturer` varchar(100) DEFAULT NULL,
  `enginetype` varchar(50) DEFAULT NULL,
  `enginemodel` varchar(50) DEFAULT NULL,
  `fueltype` varchar(50) DEFAULT NULL,
  `registrationtype` varchar(50) DEFAULT NULL,
  `registeredowner` varchar(150) DEFAULT NULL,
  `registeredownercountry` varchar(50) DEFAULT NULL,
  `operatorname` varchar(150) DEFAULT NULL,
  `operatorcountry` varchar(50) DEFAULT NULL,
  `firstregistrationdate` date DEFAULT NULL,
  `airframe` varchar(100) DEFAULT NULL,
  `propmanu` varchar(100) DEFAULT NULL,
  `propmodel` varchar(50) DEFAULT NULL,
  `typecert` varchar(50) DEFAULT NULL,
  `countrymanu` varchar(50) DEFAULT NULL,
  `yearmanu` int(11) DEFAULT NULL,
  `icaotypedesig` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `austria`;
CREATE TABLE `austria` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `bahamas`;
CREATE TABLE `bahamas` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `belgium`;
CREATE TABLE `belgium` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `bhutan`;
CREATE TABLE `bhutan` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `bolivia`;
CREATE TABLE `bolivia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `brazil`;
CREATE TABLE `brazil` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `canada`;
CREATE TABLE `canada` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `cayman_islands`;
CREATE TABLE `cayman_islands` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `chile`;
CREATE TABLE `chile` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `china`;
CREATE TABLE `china` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `costa_rica`;
CREATE TABLE `costa_rica` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `croatia`;
CREATE TABLE `croatia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `cuba`;
CREATE TABLE `cuba` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `customers`;
CREATE TABLE `customers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `stripe_customer_id` varchar(255) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `country` varchar(120) DEFAULT NULL,
  `phone` varchar(50) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `Email` (`email`),
  UNIQUE KEY `email_2` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
DROP TABLE IF EXISTS `cyprus`;
CREATE TABLE `cyprus` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `czech_republic`;
CREATE TABLE `czech_republic` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `denmark`;
CREATE TABLE `denmark` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `egypt`;
CREATE TABLE `egypt` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `estonia`;
CREATE TABLE `estonia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `ethiopia`;
CREATE TABLE `ethiopia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `flights`;
CREATE TABLE `flights` (
  `FlightID` int(11) NOT NULL AUTO_INCREMENT,
  `AircraftID` int(11) DEFAULT NULL,
  `AirlineID` int(11) DEFAULT NULL,
  `FlightNumber` varchar(255) DEFAULT NULL,
  `Registration` varchar(255) DEFAULT NULL,
  `MSN` varchar(50) DEFAULT NULL,
  `Aircraft_Type` varchar(255) DEFAULT NULL,
  `Times_Seen` int(11) DEFAULT NULL,
  `Departure` varchar(255) DEFAULT NULL,
  `Arrival` varchar(255) DEFAULT NULL,
  `Country_of_Reg` varchar(255) DEFAULT NULL,
  `Country_Flag` varchar(255) DEFAULT NULL,
  `Flight_Image` varchar(255) DEFAULT NULL,
  `Notes` text DEFAULT NULL,
  `Flight_Updated` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `Timestamp` datetime DEFAULT current_timestamp(),
  `Spotted_At` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`FlightID`),
  KEY `AirlineID` (`AirlineID`),
  CONSTRAINT `flights_ibfk_1` FOREIGN KEY (`AirlineID`) REFERENCES `airlines` (`AirlineID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `france`;
CREATE TABLE `france` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `georgia`;
CREATE TABLE `georgia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `germany`;
CREATE TABLE `germany` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `greece`;
CREATE TABLE `greece` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `guernsey`;
CREATE TABLE `guernsey` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `hungary`;
CREATE TABLE `hungary` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `iceland`;
CREATE TABLE `iceland` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `indonesia`;
CREATE TABLE `indonesia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `iran`;
CREATE TABLE `iran` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `ireland`;
CREATE TABLE `ireland` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `italy`;
CREATE TABLE `italy` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `japan`;
CREATE TABLE `japan` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `liberia`;
CREATE TABLE `liberia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `license_activity`;
CREATE TABLE `license_activity` (
  `ActivityID` int(11) NOT NULL AUTO_INCREMENT,
  `LicenseID` int(11) NOT NULL,
  `EventType` varchar(100) NOT NULL,
  `EventDetails` text DEFAULT NULL,
  `CreatedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`ActivityID`),
  KEY `LicenseID` (`LicenseID`),
  CONSTRAINT `license_activity_ibfk_1` FOREIGN KEY (`LicenseID`) REFERENCES `licenses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
DROP TABLE IF EXISTS `licenses`;
CREATE TABLE `licenses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `customer_id` int(11) NOT NULL,
  `license_type` enum('standard','professional','institutional') NOT NULL,
  `license_key` varchar(64) NOT NULL,
  `stripe_session_id` varchar(255) DEFAULT NULL,
  `stripe_payment_intent` varchar(255) DEFAULT NULL,
  `purchase_amount` decimal(10,2) DEFAULT NULL,
  `purchase_currency` varchar(10) DEFAULT 'AUD',
  `active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `expires_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `LicenseKey` (`license_key`),
  KEY `fk_license_customer` (`customer_id`),
  CONSTRAINT `fk_license_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`),
  CONSTRAINT `licenses_ibfk_1` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
DROP TABLE IF EXISTS `lithuania`;
CREATE TABLE `lithuania` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `luxembourg`;
CREATE TABLE `luxembourg` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `migrations`;
CREATE TABLE `migrations` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `migration` varchar(255) NOT NULL,
  `applied_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `migration` (`migration`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
DROP TABLE IF EXISTS `morocco`;
CREATE TABLE `morocco` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `netherlands`;
CREATE TABLE `netherlands` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `new_zealand`;
CREATE TABLE `new_zealand` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `norway`;
CREATE TABLE `norway` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `pakistan`;
CREATE TABLE `pakistan` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `panama`;
CREATE TABLE `panama` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `poland`;
CREATE TABLE `poland` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `prefixes`;
CREATE TABLE `prefixes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `country` varchar(100) DEFAULT NULL,
  `last_registry_update` date DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `qatar`;
CREATE TABLE `qatar` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `registration_prefixes`;
CREATE TABLE `registration_prefixes` (
  `Reg_Prefix` varchar(10) NOT NULL,
  `Country_of_Reg` varchar(255) NOT NULL,
  PRIMARY KEY (`Reg_Prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `romania`;
CREATE TABLE `romania` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `russia`;
CREATE TABLE `russia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `san_marino`;
CREATE TABLE `san_marino` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `saudi_arabia`;
CREATE TABLE `saudi_arabia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `id` int(11) NOT NULL DEFAULT 1,
  `show_disclaimer` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
INSERT INTO `settings` (`id`, `show_disclaimer`) VALUES (1, 1);
DROP TABLE IF EXISTS `slovakia`;
CREATE TABLE `slovakia` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `south_africa`;
CREATE TABLE `south_africa` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `south_korea`;
CREATE TABLE `south_korea` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `spain`;
CREATE TABLE `spain` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `suriname`;
CREATE TABLE `suriname` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `switzerland`;
CREATE TABLE `switzerland` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `thailand`;
CREATE TABLE `thailand` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `turkey`;
CREATE TABLE `turkey` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `united_arab_emirates`;
CREATE TABLE `united_arab_emirates` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `united_kingdom`;
CREATE TABLE `united_kingdom` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `united_states`;
CREATE TABLE `united_states` (
  `n_number` varchar(10) DEFAULT NULL,
  `serial_number` varchar(50) DEFAULT NULL,
  `mfr_mdl_code` varchar(10) DEFAULT NULL,
  `eng_mfr_mdl` varchar(50) DEFAULT NULL,
  `year_mfr` varchar(4) DEFAULT NULL,
  `type_aircraft` varchar(2) DEFAULT NULL,
  `type_engine` varchar(2) DEFAULT NULL,
  `certification` varchar(10) DEFAULT NULL,
  `status_code` varchar(2) DEFAULT NULL,
  `mode_s_code` varchar(15) DEFAULT NULL,
  `mode_s_hex` varchar(10) DEFAULT NULL,
  `air_worth_date` varchar(10) DEFAULT NULL,
  `expiration_date` varchar(10) DEFAULT NULL,
  `unique_id` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
DROP TABLE IF EXISTS `uruguay`;
CREATE TABLE `uruguay` (
  `registration` varchar(20) NOT NULL,
  `model` varchar(100) DEFAULT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `serial` varchar(50) DEFAULT NULL,
  `age` varchar(20) DEFAULT NULL,
  `icao_address` varchar(6) DEFAULT NULL,
  `date_of_registration` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  PRIMARY KEY (`registration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;
